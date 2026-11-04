from django import template
from django.utils.safestring import mark_safe

from accounts.rich_text import sanitize_rich_text

register = template.Library()


@register.filter
def safe_resume_text(value):
    return mark_safe(sanitize_rich_text(value))
