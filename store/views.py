from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Category, Product, Order, OrderItem, Wishlist


def home(request):
    categories = Category.objects.all()
    products = Product.objects.all().select_related('category')[:8]
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'store/home.html', context)


def products(request):
    category_id = request.GET.get('category', '').strip()
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '').strip()

    categories = Category.objects.all()
    products_qs = Product.objects.all().select_related('category')

    # Category filter
    if category_id:
        if category_id.isdigit():
            products_qs = products_qs.filter(category_id=int(category_id))
        else:
            products_qs = products_qs.filter(category__name__iexact=category_id)

    # Search filter
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )

    # Sorting
    if sort_by == 'price_low':
        products_qs = products_qs.order_by('price')
    elif sort_by == 'price_high':
        products_qs = products_qs.order_by('-price')
    elif sort_by == 'name':
        products_qs = products_qs.order_by('name')

    product_count = products_qs.count()

    context = {
        'categories': categories,
        'products': products_qs,
        'selected_category': category_id,
        'search_query': search_query,
        'sort_by': sort_by,
        'product_count': product_count,
    }
    return render(request, 'store/products.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product.objects.select_related('category'), id=product_id)
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'store/product_detail.html', context)


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})

    try:
        qty = int(request.POST.get('quantity', 1))
        if qty < 1:
            qty = 1
    except (ValueError, TypeError):
        qty = 1

    str_id = str(product_id)
    current_qty = cart.get(str_id, 0)
    new_qty = current_qty + qty

    # Check stock limitation
    if product.stock > 0 and new_qty > product.stock:
        new_qty = product.stock
        messages.warning(request, f"Maximum available stock for {product.name} is {product.stock}.")
    else:
        messages.success(request, f"Added {product.name} ({qty}) to your cart! 🛒")

    cart[str_id] = new_qty
    request.session['cart'] = cart
    request.session.modified = True

    if request.POST.get('buy_now'):
        return redirect('checkout')

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url == 'cart':
        return redirect('cart')
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('cart')


def update_cart(request, product_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        str_id = str(product_id)
        action = request.POST.get('action')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            product = None

        if str_id in cart:
            if action == 'increase':
                if product and product.stock > 0 and cart[str_id] >= product.stock:
                    messages.warning(request, f"Cannot add more. Only {product.stock} units in stock.")
                else:
                    cart[str_id] += 1
            elif action == 'decrease':
                cart[str_id] -= 1
                if cart[str_id] <= 0:
                    del cart[str_id]
            elif action == 'set':
                try:
                    qty = int(request.POST.get('quantity', 1))
                    if qty <= 0:
                        del cart[str_id]
                    else:
                        if product and product.stock > 0 and qty > product.stock:
                            cart[str_id] = product.stock
                        else:
                            cart[str_id] = qty
                except (ValueError, TypeError):
                    pass
            
            request.session['cart'] = cart
            request.session.modified = True
            messages.info(request, "Cart updated.")

    return redirect('cart')


def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    str_id = str(product_id)

    if str_id in cart:
        try:
            product = Product.objects.get(id=product_id)
            messages.info(request, f"Removed {product.name} from your cart.")
        except Product.DoesNotExist:
            messages.info(request, "Item removed from your cart.")
        del cart[str_id]
        request.session['cart'] = cart
        request.session.modified = True

    return redirect('cart')



def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    subtotal = 0.0

    if cart:
        product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
        products_dict = {p.id: p for p in Product.objects.filter(id__in=product_ids).select_related('category')}

        for pid_str, quantity in cart.items():
            if pid_str.isdigit():
                pid = int(pid_str)
                product = products_dict.get(pid)
                if product:
                    item_subtotal = float(product.price) * quantity
                    subtotal += item_subtotal
                    cart_items.append({
                        'product': product,
                        'quantity': quantity,
                        'subtotal': item_subtotal,
                    })

    delivery_fee = 0.0 if (subtotal >= 499 or subtotal == 0) else 50.0
    total_amount = subtotal + delivery_fee
    item_count = sum(item['quantity'] for item in cart_items)

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total': total_amount,
        'item_count': item_count,
        'free_delivery_threshold': 499,
        'delivery_shortfall': max(0, 499 - subtotal) if subtotal < 499 and subtotal > 0 else 0,
    }
    return render(request, 'store/cart.html', context)


# ==============================================================================
# Authentication Views
# ==============================================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next') or request.POST.get('next') or 'home'

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not username or not email or not password or not confirm_password:
            messages.error(request, "Please fill in all registration fields.")
            return render(request, 'store/register.html', {'next': next_url, 'username': username, 'email': email})

        if password != confirm_password:
            messages.error(request, "Passwords do not match. Please re-enter.")
            return render(request, 'store/register.html', {'next': next_url, 'username': username, 'email': email})

        if len(password) < 4:
            messages.error(request, "Password should be at least 4 characters long.")
            return render(request, 'store/register.html', {'next': next_url, 'username': username, 'email': email})

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"Username '{username}' is already taken. Please choose another.")
            return render(request, 'store/register.html', {'next': next_url, 'email': email})

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, f"Email '{email}' is already registered. Please log in.")
            return render(request, 'store/register.html', {'next': next_url, 'username': username})

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        messages.success(request, f"Welcome to SchoolKart, {username}! Your student account is ready 🎒")

        if next_url and next_url != 'None' and next_url != 'home':
            return redirect(next_url)
        return redirect('home')

    return render(request, 'store/register.html', {'next': next_url})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next') or request.POST.get('next') or 'home'

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'store/login.html', {'next': next_url, 'username': username})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}! 🎓")
            if next_url and next_url != 'None' and next_url != 'home':
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
            return render(request, 'store/login.html', {'next': next_url, 'username': username})

    return render(request, 'store/login.html', {'next': next_url})


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been safely logged out. See you next time! 🎓")
    return redirect('home')


# ==============================================================================
# Checkout & Orders Views
# ==============================================================================

@login_required(login_url='/login/')
def checkout_view(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, "Your shopping cart is empty. Add some school supplies before checking out!")
        return redirect('products')

    cart_items = []
    subtotal = 0.0
    product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
    products_dict = {p.id: p for p in Product.objects.filter(id__in=product_ids).select_related('category')}

    for pid_str, quantity in cart.items():
        if pid_str.isdigit():
            pid = int(pid_str)
            product = products_dict.get(pid)
            if product:
                item_subtotal = float(product.price) * quantity
                subtotal += item_subtotal
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'subtotal': item_subtotal,
                })

    if not cart_items:
        messages.warning(request, "Your cart items are no longer available.")
        return redirect('products')

    delivery_fee = 0.0 if subtotal >= 499 else 50.0
    total_amount = subtotal + delivery_fee

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()

        if not full_name or not address or not city or not state or not pincode or not phone_number:
            messages.error(request, "Please fill in all required shipping address fields.")
            context = {
                'cart_items': cart_items,
                'subtotal': subtotal,
                'delivery_fee': delivery_fee,
                'total': total_amount,
                'form_data': request.POST,
            }
            return render(request, 'store/checkout.html', context)

        # Create Order
        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            phone_number=phone_number,
            total_amount=total_amount,
            status='Placed'
        )

        # Create OrderItems & update stock
        for item in cart_items:
            prod = item['product']
            qty = item['quantity']
            OrderItem.objects.create(
                order=order,
                product=prod,
                product_name=prod.name,
                price=prod.price,
                quantity=qty
            )
            if prod.stock >= qty:
                prod.stock -= qty
                prod.save(update_fields=['stock'])

        # Clear session cart
        if 'cart' in request.session:
            del request.session['cart']
            request.session.modified = True

        messages.success(request, f"🎉 Order #{order.id} placed successfully! Thank you for ordering with SchoolKart.")
        return redirect('orders')

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total': total_amount,
    }
    return render(request, 'store/checkout.html', context)


@login_required(login_url='/login/')
def orders_view(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product__category').order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'store/orders.html', context)


# ==============================================================================
# Admin Management Module (Staff / Admin Only)
# ==============================================================================

def staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in with admin/staff credentials to access the Admin Management Dashboard.")
            return redirect(f"/login/?next={request.path}")
        if not request.user.is_staff:
            messages.error(request, "Access denied. Admin staff privileges are required to view the management dashboard.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@staff_required
def admin_dashboard_view(request):
    tab = request.GET.get('tab', 'overview')

    # Summary metric counts
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_orders = Order.objects.count()
    total_users = User.objects.count()

    # Low stock query (stock < 5)
    low_stock_qs = Product.objects.filter(stock__lt=5).select_related('category')
    low_stock_count = low_stock_qs.count()

    # Data lists
    products_list = Product.objects.select_related('category').order_by('-id')
    categories_list = Category.objects.annotate(prod_count=Count('product')).order_by('name')
    orders_list = Order.objects.prefetch_related('items').order_by('-created_at')
    users_list = User.objects.order_by('-date_joined')

    # Product being edited if edit_id passed
    edit_product = None
    edit_id = request.GET.get('edit_product')
    if edit_id and edit_id.isdigit():
        edit_product = Product.objects.filter(id=int(edit_id)).first()

    # Category being edited if edit_cat passed
    edit_category = None
    edit_cat_id = request.GET.get('edit_cat')
    if edit_cat_id and edit_cat_id.isdigit():
        edit_category = Category.objects.filter(id=int(edit_cat_id)).first()

    context = {
        'tab': tab,
        'total_products': total_products,
        'total_categories': total_categories,
        'total_orders': total_orders,
        'total_users': total_users,
        'low_stock_count': low_stock_count,
        'low_stock_products': low_stock_qs,
        'products_list': products_list,
        'categories_list': categories_list,
        'orders_list': orders_list,
        'users_list': users_list,
        'edit_product': edit_product,
        'edit_category': edit_category,
        'status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'store/admin_dashboard.html', context)


@staff_required
def admin_product_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category_id')
        price = request.POST.get('price', '').strip()
        stock = request.POST.get('stock', '').strip()
        description = request.POST.get('description', '').strip()

        if not name or not category_id or not price or not stock:
            messages.error(request, "Please fill in all required product fields.")
            return redirect('/admin-dashboard/?tab=products')

        try:
            category = Category.objects.get(id=int(category_id))
            product = Product.objects.create(
                name=name,
                category=category,
                price=float(price),
                stock=int(stock),
                description=description
            )
            messages.success(request, f"Product '{product.name}' created successfully! 📦")
        except Exception as e:
            messages.error(request, f"Error creating product: {str(e)}")

    return redirect('/admin-dashboard/?tab=products')


@staff_required
def admin_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category_id')
        price = request.POST.get('price', '').strip()
        stock = request.POST.get('stock', '').strip()
        description = request.POST.get('description', '').strip()

        if not name or not category_id or not price or not stock:
            messages.error(request, "Please fill in all required product fields.")
            return redirect(f'/admin-dashboard/?tab=products&edit_product={pk}')

        try:
            category = Category.objects.get(id=int(category_id))
            product.name = name
            product.category = category
            product.price = float(price)
            product.stock = int(stock)
            product.description = description
            product.save()
            messages.success(request, f"Product '{product.name}' updated successfully! ✨")
            return redirect('/admin-dashboard/?tab=products')
        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")

    return redirect(f'/admin-dashboard/?tab=products&edit_product={pk}')


@staff_required
def admin_product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    product.delete()
    messages.info(request, f"Product '{name}' was deleted.")
    return redirect('/admin-dashboard/?tab=products')


@staff_required
def admin_category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Category name cannot be empty.")
        else:
            cat, created = Category.objects.get_or_create(name=name)
            if created:
                messages.success(request, f"Category '{cat.name}' created! 🏷️")
            else:
                messages.warning(request, f"Category '{cat.name}' already exists.")
    return redirect('/admin-dashboard/?tab=categories')


@staff_required
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            category.name = name
            category.save()
            messages.success(request, f"Category updated to '{category.name}'!")
        else:
            messages.error(request, "Category name cannot be empty.")
    return redirect('/admin-dashboard/?tab=categories')



@staff_required
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.info(request, f"Category '{name}' was deleted.")
    return redirect('/admin-dashboard/?tab=categories')


@staff_required
def admin_order_status_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
        if new_status in valid_statuses:
            order.status = new_status
            order.save(update_fields=['status'])
            messages.success(request, f"Order #{order.id} status updated to '{new_status}'! 🚚")
        else:
            messages.error(request, "Invalid order status specified.")
    return redirect('/admin-dashboard/?tab=orders')
def wishlist(request):
    
    if not request.user.is_authenticated:
        return redirect("login")

    wishlist_items = Wishlist.objects.filter(
        user=request.user
    )

    return render(request, "store/wishlist.html", {
        "wishlist_items": wishlist_items
    })


def add_to_wishlist(request, product_id):

    if not request.user.is_authenticated:
        return redirect("login")

    product = get_object_or_404(Product, id=product_id)

    Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    return redirect("wishlist")


def remove_from_wishlist(request, product_id):

    if not request.user.is_authenticated:
        return redirect("login")

    Wishlist.objects.filter(
        user=request.user,
        product_id=product_id
    ).delete()

    return redirect("wishlist")