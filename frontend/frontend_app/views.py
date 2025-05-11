# frontend/frontend_app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Obtener URLs de configuración en lugar de usar constantes hardcoded
def get_service_url(service_name):
    """Función auxiliar para obtener la URL del servicio desde configuración"""
    return settings.MICROSERVICES.get(service_name, '')

def index(request):
    """Vista de la página principal"""
    return render(request, 'index.html')

def login_view(request):
    logger.debug("==== DEBUG LOGIN VIEW ====")
    logger.debug(f"Método: {request.method}")
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        logger.debug(f"Email: {email}")
        
        # Obtener URL del servicio de autenticación
        auth_url = get_service_url('AUTH_SERVICE_URL')
        login_url = f"{auth_url}login/"
        logger.debug(f"Autenticando con: {login_url}")
        
        try:
            response = requests.post(
                login_url,
                json={"email": email, "password": password},
                timeout=5  # Añadir timeout para evitar esperas largas
            )
            logger.debug(f"Código de respuesta: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Datos recibidos: {data.keys()}")
                
                # Guardar en sesión
                request.session['access_token'] = data.get('access', '')
                request.session['refresh_token'] = data.get('refresh', '')  # Guardar también el refresh token
                request.session['user_data'] = data.get('user', {})
                request.session.modified = True
                
                logger.debug("Redirigiendo a dashboard")
                messages.success(request, 'Inicio de sesión exitoso')
                return redirect('user_dashboard')
            else:
                error_msg = "Credenciales inválidas"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
                messages.error(request, error_msg)
        except requests.RequestException as e:
            logger.error(f"Error de conexión: {str(e)}")
            messages.error(request, f"Error de conexión con el servicio. Por favor, inténtelo de nuevo más tarde.")
    
    return render(request, 'registration/login.html')

def register_view(request):
    """Vista de registro de usuario"""
    if request.method == 'POST':
        # Recopilar datos del formulario
        user_data = {
            'first_name': request.POST.get('first_name'),
            'last_name': request.POST.get('last_name'),
            'id_number': request.POST.get('id_number'),
            'id_issue_date': request.POST.get('id_issue_date'),
            'email': request.POST.get('email'),
            'phone_number': request.POST.get('phone_number'),
            'password': request.POST.get('password'),
            'password_confirm': request.POST.get('password_confirm'),
        }
        
        # Validar contraseñas
        if user_data['password'] != user_data['password_confirm']:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'registration/register.html')
        
        # Llamar al servicio de autenticación
        try:
            # Obtener URL del servicio de autenticación
            auth_url = get_service_url('AUTH_SERVICE_URL')
            register_url = f"{auth_url}register/"
            
            response = requests.post(
                register_url, 
                json=user_data
            )
            
            if response.status_code == 201:
                # Registro exitoso
                messages.success(request, 'Registro exitoso, ahora puedes iniciar sesión')
                return redirect('login')
            else:
                # Error de registro
                error_data = response.json()
                for field, errors in error_data.items():
                    if isinstance(errors, list):
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
                    else:
                        messages.error(request, f'{field}: {errors}')
        except Exception as e:
            messages.error(request, f'Error de conexión: {str(e)}')
    
    return render(request, 'registration/register.html')

def logout_view(request):
    """Vista para cerrar sesión"""
    # Limpiar sesión
    if 'access_token' in request.session:
        del request.session['access_token']
    if 'refresh_token' in request.session:
        del request.session['refresh_token']
    if 'user_data' in request.session:
        del request.session['user_data']
    
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('login')

def password_reset_request(request):
    """Vista para solicitar restablecimiento de contraseña"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # Llamar al servicio de autenticación
        try:
            # Obtener URL del servicio de autenticación
            auth_url = get_service_url('AUTH_SERVICE_URL')
            reset_url = f"{auth_url}password/reset/"
            
            response = requests.post(
                reset_url, 
                json={"email": email}
            )
            
            if response.status_code == 200:
                messages.success(request, 'Se ha enviado un correo con instrucciones para restablecer tu contraseña')
                return redirect('login')
            else:
                messages.error(request, 'No se encontró ningún usuario con ese correo electrónico')
        except Exception as e:
            messages.error(request, f'Error de conexión: {str(e)}')
    
    return render(request, 'registration/password_reset.html')

def password_reset_confirm(request, token):
    """Vista para confirmar restablecimiento de contraseña"""
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validar contraseñas
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'registration/password_reset_confirm.html', {'token': token})
        
        # Llamar al servicio de autenticación
        try:
            # Obtener URL del servicio de autenticación
            auth_url = get_service_url('AUTH_SERVICE_URL')
            reset_confirm_url = f"{auth_url}password/reset/confirm/"
            
            response = requests.post(
                reset_confirm_url, 
                json={
                    "token": token,
                    "password": password,
                    "password_confirm": password_confirm
                }
            )
            
            if response.status_code == 200:
                messages.success(request, 'Contraseña restablecida correctamente')
                return redirect('login')
            else:
                error_data = response.json()
                for field, errors in error_data.items():
                    if isinstance(errors, list):
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
                    else:
                        messages.error(request, f'{field}: {errors}')
        except Exception as e:
            messages.error(request, f'Error de conexión: {str(e)}')
    
    return render(request, 'registration/password_reset_confirm.html', {'token': token})

# Elimina esta línea
# @login_required
def user_dashboard(request):
    """Vista del panel de usuario con transacciones reales"""
    logger.debug("==== DEBUG USER DASHBOARD ====")
    
    # Verificar autenticación
    if 'access_token' not in request.session or 'user_data' not in request.session:
        logger.debug("No hay sesión activa")
        messages.error(request, 'Por favor, inicia sesión para acceder a tu panel.')
        return redirect('login')
    
    # Obtener datos del usuario
    user_data = request.session.get('user_data', {})
    access_token = request.session.get('access_token', '')
    logger.debug(f"Datos de usuario: {user_data}")
    
    # Obtener transacciones del usuario
    transactions = []
    
    try:
        # Obtener URL del servicio de transacciones
        transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
        transactions_endpoint = f"{transaction_url}transactions/"
        
        # Verificar si el usuario tiene un ID
        if not user_data.get('id'):
            logger.error("ID de usuario no encontrado en los datos de sesión")
            messages.error(request, "No se pudo identificar al usuario. Por favor, vuelva a iniciar sesión.")
            return redirect('login')
        
        # Preparar la URL con el ID de usuario
        user_transactions_url = f"{transactions_endpoint}?sender_id={user_data.get('id')}"
        headers = {'Authorization': f"Bearer {access_token}"}
        
        logger.debug(f"Solicitando transacciones a: {user_transactions_url}")
        logger.debug(f"Headers: {headers}")
        
        # Realizar la solicitud con timeout para evitar bloqueos
        response = requests.get(user_transactions_url, headers=headers, timeout=5)
        
        logger.debug(f"Respuesta: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get('results', [])
            logger.debug(f"Transacciones obtenidas: {len(transactions)}")
        elif response.status_code == 401:
            logger.debug("Token inválido o expirado")
            
            # Intentar renovar el token si hay refresh token
            if 'refresh_token' in request.session:
                refresh_success = refresh_access_token(request)
                if refresh_success:
                    messages.info(request, "Sesión renovada automáticamente")
                    return redirect('user_dashboard')  # Reintentar con el token renovado
            
            # Si no hay refresh token o falló la renovación
            messages.error(request, 'Tu sesión ha expirado. Por favor, inicia sesión nuevamente.')
            return redirect('login')
        else:
            logger.error(f"Error al obtener transacciones: {response.status_code} - {response.text}")
            messages.error(request, 'Error al obtener el historial de transacciones.')
    except requests.RequestException as e:
        logger.error(f"Excepción al obtener transacciones: {str(e)}")
        messages.error(request, f'Error de conexión: {str(e)}')
    
    context = {
        'user_data': user_data,
        'transactions': transactions
    }
    
    return render(request, 'user_panel/dashboard.html', context)

def refresh_access_token(request):
    """Función para renovar el token de acceso usando el refresh token"""
    refresh_token = request.session.get('refresh_token')
    if not refresh_token:
        return False
    
    try:
        auth_url = get_service_url('AUTH_SERVICE_URL')
        refresh_url = f"{auth_url}token/refresh/"
        
        response = requests.post(
            refresh_url,
            json={"refresh": refresh_token},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            request.session['access_token'] = data.get('access', '')
            request.session.modified = True
            return True
    except:
        pass
    
    return False

def transaction_form(request):
    """Vista del formulario de transacción con comunicación real"""
    logger.debug("==== DEBUG TRANSACTION FORM ====")
    
    # Verificar autenticación
    if 'access_token' not in request.session or 'user_data' not in request.session:
        logger.debug("No hay sesión activa")
        messages.error(request, 'Por favor, inicia sesión para realizar una transacción.')
        return redirect('login')
    
    # Obtener datos del usuario
    user_data = request.session.get('user_data', {})
    access_token = request.session.get('access_token', '')
    logger.debug(f"Datos de usuario: {user_data}")
    
    # Si es POST, procesar el formulario
    if request.method == 'POST':
        logger.debug("Procesando formulario POST")
        # Obtener datos del formulario
        receiver_name = request.POST.get('receiver_name')
        amount = request.POST.get('amount')
        message = request.POST.get('message', '')
        
        logger.debug(f"Datos de transacción: Receptor={receiver_name}, Monto={amount}, Mensaje={message}")
        
        # Validar datos básicos
        errors = []
        if not receiver_name:
            errors.append('El nombre del destinatario es obligatorio.')
        
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append('El monto debe ser mayor que cero.')
            
            # Verificar saldo suficiente
            user_balance = float(user_data.get('balance', 0))
            if amount > user_balance:
                errors.append('Saldo insuficiente para realizar esta transacción.')
        except (ValueError, TypeError):
            errors.append('El monto debe ser un número válido.')
        
        # Si hay errores, mostrarlos
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'user_panel/transaction_form.html', {'user_data': user_data})
        
        # Si no hay errores, crear la transacción en el microservicio
        try:
            # Preparar datos para la solicitud
            transaction_data = {
                'sender_id': str(user_data.get('id')),
                'sender_name': f"{user_data.get('first_name')} {user_data.get('last_name')}",
                'receiver_name': receiver_name,
                'amount': amount,
                'message': message
            }
            
            # Configurar headers con token JWT
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            # Obtener URL del servicio de transacciones
            transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
            transactions_endpoint = f"{transaction_url}transactions/"
            
            logger.debug(f"Enviando solicitud a {transactions_endpoint}")
            logger.debug(f"Datos: {transaction_data}")
            
            # Realizar la solicitud POST con timeout
            response = requests.post(
                transactions_endpoint, 
                json=transaction_data,
                headers=headers,
                timeout=10  # Dar más tiempo a esta operación
            )
            
            logger.debug(f"Respuesta: {response.status_code}")
            logger.debug(f"Contenido: {response.text[:500]}")
            
            if response.status_code == 201:  # Creado exitosamente
                transaction = response.json()
                
                # Actualizar el saldo del usuario en la sesión
                user_data['balance'] = str(float(user_data.get('balance', 0)) - amount)
                request.session['user_data'] = user_data
                request.session.modified = True
                
                # Mensaje según el estado de la transacción
                if transaction.get('status') == 'fraudulent':
                    messages.warning(request, 'Transacción marcada como posiblemente fraudulenta. Un administrador revisará el caso.')
                else:
                    messages.success(request, 'Transacción realizada con éxito.')
                
                return redirect('user_dashboard')
            elif response.status_code == 401:
                # Token expirado, intentar renovar
                if refresh_access_token(request):
                    messages.info(request, "Por favor, intente de nuevo. Su sesión ha sido renovada.")
                else:
                    messages.error(request, 'Su sesión ha expirado. Por favor, inicie sesión nuevamente.')
                    return redirect('login')
            else:
                logger.error(f"Error en la creación de la transacción: {response.text}")
                error_msg = "Error al procesar la transacción"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and 'detail' in error_data:
                        error_msg = error_data['detail']
                except:
                    pass
                messages.error(request, error_msg)
                
        except requests.RequestException as e:
            logger.error(f"Excepción al crear transacción: {str(e)}")
            messages.error(request, f'Error de conexión: {str(e)}')
    
    # Si es GET, mostrar formulario
    return render(request, 'user_panel/transaction_form.html', {'user_data': user_data})

@login_required
def admin_dashboard(request):
    """Vista del panel de administrador"""
    # Verificar si es admin
    user_data = request.session.get('user_data', {})
    if user_data.get('email') != 'admin@example.com':
        messages.error(request, 'Acceso denegado')
        return redirect('user_dashboard')
    
    # Inicializar estructura de estadísticas
    stats = {
        'today': {
            'total': 0,
            'legitimate': 0,
            'possibly_fraudulent': 0,
            'fraudulent': 0,
            'total_amount': 0.0,
        },
        'last_week': {
            'total': 0,
            'legitimate': 0,
            'possibly_fraudulent': 0,
            'fraudulent': 0,
            'total_amount': 0.0,
            'daily_distribution': {},
        },
        'last_month': {
            'total': 0,
            'legitimate': 0,
            'possibly_fraudulent': 0,
            'fraudulent': 0,
            'total_amount': 0.0,
            'daily_distribution': {},
        }
    }
    
    # Obtener estadísticas de transacciones
    headers = {'Authorization': f"Bearer {request.session.get('access_token')}"}
    
    try:
        # Obtener la URL del servicio de transacciones
        transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
        stats_url = f"{transaction_url}transactions/stats/"
        
        # Obtener estadísticas
        response = requests.get(
            stats_url, 
            headers=headers
        )
        
        if response.status_code == 200:
            api_stats = response.json()
            # Actualizar con datos reales si están disponibles
            if api_stats:
                stats.update(api_stats)
        else:
            messages.error(request, 'Error al obtener estadísticas')
    except Exception as e:
        messages.error(request, f'Error de conexión: {str(e)}')
    
    # Obtener transacciones fraudulentas para alertas
    fraud_transactions = []
    try:
        # Obtener la URL del servicio de transacciones
        transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
        fraud_url = f"{transaction_url}transactions/?status=fraudulent"
        
        response = requests.get(
            fraud_url, 
            headers=headers
        )
        
        if response.status_code == 200:
            fraud_data = response.json()
            fraud_transactions = fraud_data.get('results', [])
    except Exception as e:
        pass  # Silenciosamente manejar errores aquí
    
    context = {
        'user_data': user_data,
        'stats': stats,
        'fraud_transactions': fraud_transactions
    }
    
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
def admin_transactions(request):
    """Vista de transacciones para el administrador"""
    # Verificar si es admin
    user_data = request.session.get('user_data', {})
    if user_data.get('email') != 'admin@example.com':
        messages.error(request, 'Acceso denegado')
        return redirect('user_dashboard')
    
    # Obtener parámetros de filtro
    status_filter = request.GET.get('status', '')
    min_amount = request.GET.get('min_amount', '')
    max_amount = request.GET.get('max_amount', '')
    
    # Obtener la URL del servicio de transacciones
    transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
    
    # Construir URL con filtros
    url = f"{transaction_url}transactions/"
    params = {}
    
    if status_filter:
        params['status'] = status_filter
    if min_amount:
        params['min_amount'] = min_amount
    if max_amount:
        params['max_amount'] = max_amount
    
    # Obtener transacciones
    headers = {'Authorization': f"Bearer {request.session.get('access_token')}"}
    
    try:
        if min_amount or max_amount:
            filter_url = f"{transaction_url}transactions/filter_by_amount/"
            response = requests.get(
                filter_url, 
                params=params,
                headers=headers
            )
        else:
            response = requests.get(
                url, 
                params=params,
                headers=headers
            )
        
        if response.status_code == 200:
            if min_amount or max_amount:
                transactions = response.json()
            else:
                transactions = response.json().get('results', [])
        else:
            transactions = []
            messages.error(request, 'Error al obtener transacciones')
    except Exception as e:
        transactions = []
        messages.error(request, f'Error de conexión: {str(e)}')
    
    context = {
        'user_data': user_data,
        'transactions': transactions,
        'status_filter': status_filter,
        'min_amount': min_amount,
        'max_amount': max_amount
    }
    
    return render(request, 'admin_panel/transactions.html', context)

@csrf_exempt
def update_transaction_status(request):
    """Vista para actualizar el estado de una transacción (AJAX)"""
    if request.method == 'POST':
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        
        # Obtener la URL del servicio de transacciones
        transaction_url = get_service_url('TRANSACTION_SERVICE_URL')
        update_url = f"{transaction_url}transactions/{transaction_id}/update_status/"
        
        # Actualizar estado
        headers = {'Authorization': f"Bearer {request.session.get('access_token')}"}
        
        try:
            response = requests.post(
                update_url, 
                json={"status": status},
                headers=headers
            )
            
            if response.status_code == 200:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Error al actualizar estado'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# Create your views here.