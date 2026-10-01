def cart_context(request):
    cart = request.session.get('cart', {})
    if isinstance(cart, dict):
        total_items = sum(cart.values())
    else:
        total_items = 0
    return {
        'cart_item_count': total_items
    }
