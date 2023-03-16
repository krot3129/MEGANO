from django.shortcuts import render, redirect
from django.views import generic
from django.shortcuts import get_object_or_404
from django.forms.utils import ErrorList
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login
# from django.contrib.auth.mixins import LoginRequiredMixin
from product.models import Offer
from .models import OrderItem, Order
from users.models import CustomUser
from product.services import get_category
from .forms import OrderUserCreateForm, OrderPaymentCreateForm, OrderDeliveryCreateForm, OrderCardForm
from cart.service import Cart
from . import tasks
from django.core.cache import cache
from django.conf import settings
from random import randint
# from django.contrib.auth import views as aut_view
# import redis
# from django.core.cache import cache
# from django.conf import settings
# from django.core.cache.backends.base import DEFAULT_TIMEOUT
# CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)
# caching = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
# caching = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)


class HistoryOrderView(generic.ListView):
    model = Order
    template_name = 'orders/history_order.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['orders'] = Order.objects.filter(email=self.request.user)
        context['categories'] = get_category()
        return context


class HistoryOrderDetailView(generic.DetailView):
    model = Order
    template_name = 'orders/history_order_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = get_category()
        context['offers'] = OrderItem.objects.filter(order=kwargs['object'])
        return context


def order_valid_post_check(request, form):
    if not request.user.is_anonymous:
        cache.set('first_name', form.cleaned_data.get('first_name'))
        cache.set('last_name', form.cleaned_data.get('last_name'))
        cache.set('email', request.user.email)
        cache.set('number', form.cleaned_data.get('number'))
    else:
        # Если пользователь не авторизован, но существует
        if CustomUser.objects.filter(email=form.cleaned_data['email']).exists():
            form._errors["email"] = ErrorList([_(u"Пользователь уже существует")])
            # Выводить форму входа
            return render(request, 'orders/new-order.html',
                          {'form': form, 'categories': get_category()})
        # Если пользователь не авторизован и не существует
        else:
            if form.cleaned_data.get('password1') == form.cleaned_data.get('password2'):
                if form.cleaned_data.get('password1') == '':
                    form._errors["email"] = ErrorList(
                        [_(u"Данный пользователь не зарегистрирован, Введите пароль")]
                    )
                    return render(request, 'orders/new-order.html',
                                  {'form': form, 'categories': get_category()})
                if len(form.cleaned_data.get('password1')) < 8:
                    form._errors["password1"] = ErrorList(
                        [_(u"Пароль должен быть длиннее 8 символов")]
                    )
                    return render(request, 'orders/new-order.html',
                                  {'form': form, 'categories': get_category()})
                user = get_user_model().objects.create_user(phone=form.cleaned_data.get('number'),
                                                            email=form.cleaned_data.get('email'),
                                                            password=form.cleaned_data.get('password1'))
                user.save()
                user = authenticate(email=form.cleaned_data.get('email'),
                                    password=form.cleaned_data.get('password1'))
                login(request, user)
                cache.set('first_name', form.cleaned_data.get('first_name'))
                cache.set('last_name', form.cleaned_data.get('last_name'))
                cache.set('email', request.user.email)
                cache.set('number', form.cleaned_data.get('number'))
            else:
                form._errors["password1"] = ErrorList([_(u"Пароли не совпадают")])
                return render(request, 'orders/new-order.html',
                              {'form': form, 'categories': get_category()})
    return redirect('order_create_delivery')


def order_password(request, form):
    if form.cleaned_data.get('password1') == '':
        form._errors["email"] = ErrorList(
            [_(u"Данный пользователь не зарегистрирован, Введите пароль")]
        )
        return render(request, 'orders/new-order.html',
                      {'form': form, 'categories': get_category()})
    if len(form.cleaned_data.get('password1')) < 8:
        form._errors["password1"] = ErrorList(
            [_(u"Пароль должен быть длиннее 8 символов")]
        )
        return render(request, 'orders/new-order.html',
                      {'form': form, 'categories': get_category()})


def order_create(request): # noqa: max-complexity: 13
    if request.method == 'POST':
        if 'password' in request.POST:
            user = authenticate(email=request.POST.get('email'), password=request.POST.get('password'))
            if user is not None:
                login(request, user)
                return redirect('order_create')
        form = OrderUserCreateForm(request.POST)
        if form.is_valid():
            if not request.user.is_anonymous:
                cache.set('first_name', form.cleaned_data.get('first_name'))
                cache.set('last_name', form.cleaned_data.get('last_name'))
                cache.set('email', request.user.email)
                cache.set('number', form.cleaned_data.get('number'))
            else:
                # Если пользователь не авторизован, но существует
                if CustomUser.objects.filter(email=form.cleaned_data['email']).exists():
                    form._errors["email"] = ErrorList([_(u"Пользователь уже существует")])
                    # Выводить форму входа
                    return render(request, 'orders/new-order.html',
                                  {'form': form, 'categories': get_category()})
                # Если пользователь не авторизован и не существует
                else:
                    if form.cleaned_data.get('password1') == form.cleaned_data.get('password2'):
                        if form.cleaned_data.get('password1') == '':
                            form._errors["email"] = ErrorList(
                                [_(u"Данный пользователь не зарегистрирован, Введите пароль")]
                            )
                            return render(request, 'orders/new-order.html',
                                          {'form': form, 'categories': get_category()})
                        if len(form.cleaned_data.get('password1')) < 8:
                            form._errors["password1"] = ErrorList(
                                [_(u"Пароль должен быть длиннее 8 символов")]
                            )
                            return render(request, 'orders/new-order.html',
                                          {'form': form, 'categories': get_category()})
                        user = get_user_model().objects.create_user(phone=form.cleaned_data.get('number'),
                                                                    email=form.cleaned_data.get('email'),
                                                                    password=form.cleaned_data.get('password1'))
                        user.save()
                        user = authenticate(email=form.cleaned_data.get('email'),
                                            password=form.cleaned_data.get('password1'))
                        login(request, user)
                        cache.set('first_name', form.cleaned_data.get('first_name'))
                        cache.set('last_name', form.cleaned_data.get('last_name'))
                        cache.set('email', request.user.email)
                        cache.set('number', form.cleaned_data.get('number'))
                    else:
                        form._errors["password1"] = ErrorList([_(u"Пароли не совпадают")])
                        return render(request, 'orders/new-order.html',
                                      {'form': form, 'categories': get_category()})
            return redirect('order_create_delivery')
    else:
        if request.user.is_authenticated:
            data = {'number': request.user.phone,
                    'email': request.user.email,
                    }
            form = OrderUserCreateForm(data)
            if request.user.phone:
                form.fields['number'].widget.attrs['readonly'] = True
            form.fields['email'].widget.attrs['readonly'] = True
        else:
            form = OrderUserCreateForm
    return render(request, 'orders/new-order.html',
                  {'form': form, 'categories': get_category()})


def order_create_delivery(request):
    if request.method == 'POST':
        form = OrderDeliveryCreateForm(request.POST)
        if form.is_valid():
            cache.set('delivery', form.cleaned_data.get('delivery'))
            cache.set('city', form.cleaned_data.get('city'))
            cache.set('address', form.cleaned_data.get('address'))
            return redirect('order_type_payment')
    else:
        form = OrderDeliveryCreateForm
    return render(request, 'orders/order-delivery.html',
                  {'form': form, 'categories': get_category()})


def order_type_payment(request):
    if request.method == 'POST':
        form = OrderPaymentCreateForm(request.POST)
        if form.is_valid():
            cache.set('payment', form.cleaned_data.get('payment'))
            return redirect('order_create_payment')
    else:
        form = OrderPaymentCreateForm
    return render(request, 'orders/order-payment.html',
                  {'form': form, 'categories': get_category()})


def order_create_payment(request):
    cart = Cart(request)
    total = cart.get_total_price()
    seller = []
    elem = request.session.get(settings.ADMIN_SETTINGS_ID)
    if elem is None or elem.get('DELIVERY_PRICE') is None:
        delivery_price = settings.DELIVERY_PRICE
    else:
        delivery_price = elem['DELIVERY_PRICE']
    if elem is None or elem.get('DELIVERY_STOCK') is None:
        delivery_stock = settings.DELIVERY_STOCK
    else:
        delivery_stock = elem['DELIVERY_STOCK']
    for item in cart:
        print(item['product'].id)
        seller.append(Offer.objects.get(id=item['product'].id).seller)
        seller = set(seller)
    if total < delivery_price or len(seller) > 1:
        total += delivery_stock
    if request.method == 'POST':
        form = OrderCardForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(first_name=cache.get('first_name'),
                                         last_name=cache.get('last_name'),
                                         email=cache.get('email'),
                                         number=cache.get('number'),
                                         delivery=cache.get('delivery'),
                                         city=cache.get('city'),
                                         address=cache.get('address'),
                                         payment=cache.get('payment'),
                                         card_number=form.cleaned_data.get('card_number'),
                                         total=total)
            for item in cart.cart:
                OrderItem.objects.create(order=order,
                                         offer=Offer.objects.get(id=int(item)),
                                         price=float(cart.cart[item]['price']),
                                         quantity=cart.cart[item]['quantity'],
                                         )
            cart.clear()
            cache.close()
            tasks.payment.delay(order.pk)
            return redirect('wait-payment', pk=order.pk)
    else:
        if cache.get('payment') == 'F':
            form = OrderCardForm({'card_number': randint(10000000, 99999999)})
            return render(request, 'orders/order.html',
                          {'form': form, 'categories': get_category(), 'rand': True})
        else:
            form = OrderCardForm()

    return render(request, 'orders/order.html',
                  {'form': form, 'categories': get_category()})


def wait_payment(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'orders/created.html', {'order': order})
