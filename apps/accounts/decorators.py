from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def user_type_required(*user_types):
    """Decorator to check if user has required user type"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            if request.user.user_type not in user_types and not request.user.is_superuser:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def owner_required(view_func):
    """Decorator for owner-only views"""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.user_type == 'HOUSE_OWNER' or u.is_superuser),
        login_url='accounts:login'
    )
    return decorator(view_func)


def tenant_required(view_func):
    """Decorator for tenant-only views"""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.user_type == 'TENANT' or u.is_superuser),
        login_url='accounts:login'
    )
    return decorator(view_func)


def caretaker_required(view_func):
    """Decorator for caretaker-only views"""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.user_type == 'CARETAKER' or u.is_superuser),
        login_url='accounts:login'
    )
    return decorator(view_func)


def superadmin_required(view_func):
    """Decorator for superadmin-only views"""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_superuser,
        login_url='accounts:login'
    )
    return decorator(view_func)