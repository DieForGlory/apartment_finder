from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required
from app.services import selection_service, complex_calc_service

complex_calc_bp = Blueprint('complex_calc', __name__, template_folder='templates')

@complex_calc_bp.route('/complex-calculations/<int:sell_id>')
@login_required
def show_page(sell_id):
    """Отображает страницу сложных расчетов."""
    card_data = selection_service.get_apartment_card_data(sell_id)
    if not card_data.get('apartment'):
        flash("Объект не найден.", "danger")
        return redirect(url_for('main.selection'))
    return render_template('complex_calculations.html', title="Сложные расчёты", data=card_data)

@complex_calc_bp.route('/calculate-installment', methods=['POST'])
@login_required
def calculate_installment():
    """Обрабатывает AJAX-запрос для расчета рассрочки."""
    data = request.get_json()
    try:
        sell_id = data.get('sell_id')
        term = int(data.get('term'))
        # Собираем доп. скидки из запроса
        additional_discounts = {k: v for k, v in data.get('additional_discounts', {}).items() if v > 0}

        result = complex_calc_service.calculate_installment_plan(sell_id, term, additional_discounts)
        return jsonify(success=True, data=result)
    except (ValueError, TypeError) as e:
        return jsonify(success=False, error=str(e)), 400
    except Exception as e:
        # Логирование полной ошибки на сервере
        current_app.logger.error(f"Critical error in installment calculation: {e}")
        return jsonify(success=False, error="Произошла внутренняя ошибка на сервере."), 500

@complex_calc_bp.route('/calculate-dp-installment', methods=['POST'])
@login_required
def calculate_dp_installment():
    """Обрабатывает AJAX-запрос для расчета рассрочки на ПВ."""
    data = request.get_json()
    try:
        result = complex_calc_service.calculate_dp_installment_plan(
            sell_id=data.get('sell_id'),
            term_months=int(data.get('term')),
            dp_amount=float(data.get('dp_amount')),
            dp_type=data.get('dp_type'),
            additional_discounts={k: v for k, v in data.get('additional_discounts', {}).items() if v > 0}
        )
        return jsonify(success=True, data=result)
    except (ValueError, TypeError) as e:
        return jsonify(success=False, error=str(e)), 400
    except Exception as e:
        current_app.logger.error(f"Critical error in DP installment calculation: {e}")
        return jsonify(success=False, error="Произошла внутренняя ошибка на сервере."), 500