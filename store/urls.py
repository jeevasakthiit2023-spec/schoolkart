from django.urls import path
from .views import (
    home,
    products,
    product_detail,
    cart_view,
    add_to_cart,
    remove_from_cart,
    update_cart,
    register_view,
    login_view,
    logout_view,
    checkout_view,
    orders_view,
    admin_dashboard_view,
    admin_product_add,
    admin_product_edit,
    admin_product_delete,
    admin_category_add,
    admin_category_edit,
    admin_category_delete,
    admin_order_status_update,
    wishlist,
    add_to_wishlist,
    remove_from_wishlist,
)

urlpatterns = [
    path('', home, name='home'),
    path('products/', products, name='products'),
    path('product/<int:product_id>/', product_detail, name='product_detail'),

    path('cart/', cart_view, name='cart'),
    path('cart/add/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:product_id>/', update_cart, name='update_cart'),

    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    path('checkout/', checkout_view, name='checkout'),
    path('orders/', orders_view, name='orders'),

    # Wishlist
    path('wishlist/', wishlist, name='wishlist'),
    path('wishlist/add/<int:product_id>/', add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', remove_from_wishlist, name='remove_from_wishlist'),

    # Admin Management Module
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/product/add/', admin_product_add, name='admin_product_add'),
    path('admin-dashboard/product/<int:pk>/edit/', admin_product_edit, name='admin_product_edit'),
    path('admin-dashboard/product/<int:pk>/delete/', admin_product_delete, name='admin_product_delete'),
    path('admin-dashboard/category/add/', admin_category_add, name='admin_category_add'),
    path('admin-dashboard/category/<int:pk>/edit/', admin_category_edit, name='admin_category_edit'),
    path('admin-dashboard/category/<int:pk>/delete/', admin_category_delete, name='admin_category_delete'),
    path('admin-dashboard/order/<int:pk>/status/', admin_order_status_update, name='admin_order_status_update'),
]