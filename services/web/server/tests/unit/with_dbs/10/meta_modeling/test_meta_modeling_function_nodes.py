# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


def create(iterable_func, input_values):

    # TODO: process input to iterable_func inputs
    def iter_node():
        for output_values in iterable_func(**input_values):
            # map each func output into a node output
            yield {f"out_{i}": value for i, value in enumerate(output_values, start=1)}

    return iter_node


# given a function signature -> inputs and outputs for ServiceDockerData (schema)
# of the service
#
#
