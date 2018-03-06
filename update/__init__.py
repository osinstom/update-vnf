#######################################################################
#
#   Copyright (c) 2016 Orange
#   valentin.boucher@orange.com
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
########################################################################


from cloudify.decorators import workflow
from cloudify.workflows import ctx
from cloudify.workflows.tasks_graph import forkjoin
import pprint

@workflow
def run_operation(operation, nodes_types_list, nodes_types_dependency, relations_unlink, operation_kwargs, **kwargs):
    graph = ctx.graph_mode()
    send_event_starting_tasks = {}
    send_event_done_tasks = {}


    for node_type_update in nodes_types_list:
        for node in ctx.nodes:
            if node.type == node_type_update:
                for instance in node.instances:
                    send_event_starting_tasks[instance.id] = instance.send_event('Starting to run operation')
                    send_event_done_tasks[instance.id] = instance.send_event('Done running operation')

    previous_task = None
    for node_type_update in nodes_types_list:
        if not nodes_types_dependency:
            previous_task = None
        for node in ctx.nodes:
            if node.type == node_type_update:
                for instance in node.instances:

                    sequence = graph.sequence()

                    #operation_task = instance.execute_operation(operation, kwargs=operation_kwargs)

                    forkjoin_tasks_unlink = []
                    for relationship in instance.relationships:
                        ctx.logger.info(relationship.relationship.target_id)
                        if relationship.relationship.target_id in relations_unlink:
                            operation_unlink = 'cloudify.interfaces.relationship_lifecycle.unlink'
                            forkjoin_tasks_unlink.append(relationship.execute_source_operation(operation_unlink))
                            forkjoin_tasks_unlink.append(relationship.execute_target_operation(operation_unlink))
                    operation_task_unlink = forkjoin(*forkjoin_tasks_unlink)

                    forkjoin_tasks_link = []
                    for relationship in instance.relationships:
                        if relationship.relationship.target_id in relations_unlink:
                            ctx.logger.info('rel op')
                            operation_link = 'cloudify.interfaces.relationship_lifecycle.establish'
                            forkjoin_tasks_link.append(relationship.execute_source_operation(operation_link))
                            forkjoin_tasks_link.append(relationship.execute_target_operation(operation_link))
                    operation_task_link = forkjoin(*forkjoin_tasks_link)

                    sequence.add(
                        send_event_starting_tasks[instance.id],
                        operation_task_unlink,
                        instance.execute_operation('cloudify.interfaces.lifecycle.stop', kwargs=operation_kwargs),
                        instance.execute_operation('cloudify.interfaces.lifecycle.upgrade', kwargs=operation_kwargs),
                        instance.execute_operation('cloudify.interfaces.lifecycle.start', kwargs=operation_kwargs),
                        operation_task_link,
                        send_event_done_tasks[instance.id])

                    if previous_task:
                        graph.add_dependency(send_event_starting_tasks.get(instance.id), send_event_done_tasks.get(previous_task))
                        with open("/etc/cloudify/file_out.txt", "w") as f:
                            pprint.pprint(previous_task, f)
                    previous_task = instance.id


    return graph.execute()
