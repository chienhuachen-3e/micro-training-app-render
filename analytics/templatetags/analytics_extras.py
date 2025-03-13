from django import template

register = template.Library()

@register.filter
def call(obj, *args, **kwargs):
    """
    调用对象的方法并传递参数
    """
    if len(args) == 1:
        return obj(args[0])
    return obj(*args, **kwargs)

@register.filter
def completion_rate(program, user):
    """
    获取特定用户的程序完成率
    """
    return program.get_completion_rate(user)