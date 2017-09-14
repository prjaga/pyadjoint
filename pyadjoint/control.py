from .overloaded_type import OverloadedType


class Control(object):
    """Defines a control variable from an OverloadedType.

    The control object references a specific node on the Tape.
    For mutable OverloadedType instances the Control only represents
    the value at the time of initialization.

    Example:
        Given a mutable OverloadedType instance u.

        >>> u = MutableFloat(1.0)
        >>> float(u)
        1.0
        >>> c1 = Control(u)
        >>> u.add_in_place(2.0)
        >>> c2 = Control(u)
        >>> float(u)
        3.0
        >>> c1.data()
        1.0
        >>> c2.data()
        3.0

        Now c1 represents the node prior to the add_in_place Block,
        while c2 represents the node after the add_in_place Block.
        Creating a `ReducedFunctional` with c2 as Control results in
        a reduced problem without the add_in_place Block, while a ReducedFunctional
        with c1 as Control results in a forward model including the add_in_place.

    Args:
        control (OverloadedType): The OverloadedType instance to define this control from.

    """
    def __init__(self, control):
        self.control = control
        self.block_output = control.get_block_output()

    def data(self):
        return self.block_output.checkpoint

    def get_derivative(self, options={}):
        return self.control._ad_convert_type(self.block_output.adj_value, options=options)

    def get_hessian(self, options={}):
        return self.control._ad_convert_type(self.block_output.hessian_value, options=options)

    def update(self, value):
        # In the future we might want to call a static method
        # for converting a value to the correct type.
        # As this might depend on the OverloadedType control.
        if isinstance(value, OverloadedType):
            self.block_output.control_value = value._ad_create_checkpoint()
        else:
            self.block_output.control_value = value

    def __getattr__(self, item):
        return getattr(self.control, item)

    def activate_recompute_flag(self):
        self.block_output.is_control = True
        self.block_output.depends_on_control = True


