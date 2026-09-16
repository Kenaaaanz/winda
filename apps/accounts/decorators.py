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


def scout_required(view_func):
    """Allow only verified property scouts and superadmins."""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.is_superuser or (
            u.user_type == 'PROPERTY_SCOUT' and u.verification_status == 'VERIFIED'
        )),
        login_url='accounts:login'
    )
    return decorator(view_func)


def listing_required(view_func):
    """Allow verified owners, verified scouts, and superadmins to submit listings."""
    decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.is_superuser or (
            u.user_type in ('HOUSE_OWNER', 'PROPERTY_SCOUT') and u.verification_status == 'VERIFIED'
        )),
        login_url='accounts:login'
    )
    return decorator(view_func)