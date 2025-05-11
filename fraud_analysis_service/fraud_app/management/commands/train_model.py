# fraud_analysis_service/fraud_app/management/commands/train_model.py

from django.core.management.base import BaseCommand
from fraud_app.ml_model.train import train_model
import pandas as pd
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Entrena el modelo de detección de fraude'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data_file',
            type=str,
            help='Ruta al archivo CSV con datos para entrenamiento (opcional)'
        )
        parser.add_argument(
            '--synthetic',
            action='store_true',
            help='Usar datos sintéticos para entrenamiento'
        )
        parser.add_argument(
            '--samples',
            type=int,
            default=1000,
            help='Número de muestras sintéticas a generar'
        )

    def handle(self, *args, **options):
        self.stdout.write('Iniciando entrenamiento del modelo...')
        
        data_file = options.get('data_file')
        use_synthetic = options.get('synthetic')
        n_samples = options.get('samples')
        
        try:
            if data_file and os.path.exists(data_file):
                self.stdout.write(f'Cargando datos desde archivo: {data_file}')
                try:
                    # Cargar datos desde el archivo CSV
                    df = pd.read_csv(data_file)
                    
                    # Verificar que el DataFrame tenga las columnas necesarias
                    required_columns = [
                        'amount', 'hour_of_day', 'day_of_week', 'is_weekend',
                        'sender_avg_amount', 'sender_transaction_count',
                        'sender_transaction_frequency', 'amount_deviation',
                        'is_fraud'
                    ]
                    
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        self.stdout.write(self.style.ERROR(
                            f'El archivo no contiene las columnas requeridas: {missing_columns}'
                        ))
                        return
                    
                    # Entrenar modelo con los datos cargados
                    result = train_model(df)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'Modelo entrenado exitosamente: {result["version"]}'
                    ))
                    self.stdout.write(f'Accuracy: {result["accuracy"]:.4f}')
                    self.stdout.write(f'Precision: {result["precision"]:.4f}')
                    self.stdout.write(f'Recall: {result["recall"]:.4f}')
                    self.stdout.write(f'F1 Score: {result["f1_score"]:.4f}')
                    self.stdout.write(f'AUC: {result["auc"]:.4f}')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error al cargar los datos: {str(e)}'))
                    raise
            elif use_synthetic:
                self.stdout.write(f'Generando {n_samples} datos sintéticos para entrenamiento')
                # Entrenar con datos sintéticos
                result = train_model(None)  # La función train_model generará datos sintéticos
                
                self.stdout.write(self.style.SUCCESS(
                    f'Modelo entrenado exitosamente con datos sintéticos: {result["version"]}'
                ))
                self.stdout.write(f'Accuracy: {result["accuracy"]:.4f}')
                self.stdout.write(f'Precision: {result["precision"]:.4f}')
                self.stdout.write(f'Recall: {result["recall"]:.4f}')
                self.stdout.write(f'F1 Score: {result["f1_score"]:.4f}')
                self.stdout.write(f'AUC: {result["auc"]:.4f}')
            else:
                self.stdout.write(self.style.WARNING(
                    'No se especificó archivo de datos ni --synthetic. '
                    'Usando datos históricos de la base de datos.'
                ))
                
                # Entrenar con datos de la base de datos
                from fraud_app.models import TransactionFeature
                if TransactionFeature.objects.count() > 50:
                    self.stdout.write(f'Usando {TransactionFeature.objects.count()} registros de la base de datos')
                    
                    # Crear DataFrame con datos de transacciones
                    data = []
                    for feature in TransactionFeature.objects.all():
                        data.append({
                            'amount': feature.amount,
                            'hour_of_day': feature.hour_of_day,
                            'day_of_week': feature.day_of_week,
                            'is_weekend': feature.is_weekend,
                            'sender_avg_amount': feature.sender_avg_amount,
                            'sender_transaction_count': feature.sender_transaction_count,
                            'sender_transaction_frequency': feature.sender_transaction_frequency,
                            'amount_deviation': feature.amount_deviation,
                            'is_fraud': feature.is_fraud
                        })
                    
                    if data:
                        df = pd.DataFrame(data)
                        result = train_model(df)
                        
                        self.stdout.write(self.style.SUCCESS(
                            f'Modelo entrenado exitosamente: {result["version"]}'
                        ))
                        self.stdout.write(f'Accuracy: {result["accuracy"]:.4f}')
                    else:
                        self.stdout.write(self.style.ERROR('No se pudieron obtener datos suficientes'))
                        # Usamos datos sintéticos como fallback
                        self.stdout.write('Usando datos sintéticos como alternativa')
                        result = train_model(None)
                else:
                    self.stdout.write(self.style.WARNING(
                        'No hay suficientes datos en la base de datos. Usando datos sintéticos.'
                    ))
                    result = train_model(None)
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante el entrenamiento: {str(e)}'))
            logger.exception("Error durante el entrenamiento del modelo")
            return