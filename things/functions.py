
def repr_helper(self):
    return f"{self.__class__.__name__}({', '.join(str(k) + '=' + str(v) for k, v in self.as_dict().items())})"


def dt_to_std_str(some_dt):
    return some_dt.strftime("%Y_%m_%d-%H_%M_%S_%f")
