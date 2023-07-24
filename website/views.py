# stores standard routes for website
# ie. where users can go to 
from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, send_file
from flask_login import login_required, current_user
from .models import Note
from . import db
import json, os

from backend.shipping_objects import *
saver = Save_Data(filename="pickle_data.json")
shipment = saver.load_data(restart_data=True)

print('---------RESTARTING VIEWS')
# blueprint defines a bunch of URLs
# naming it 'views' is optional but simplifies things
views = Blueprint('views', __name__)

# define route for homepage
# home() will run whenever user goes to homepage
# (ie. root directory '/')
# view orders from here
@views.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        pass
    # applies html template to homepage
    # passes user as a variable to be used in template
    print(f'----------- PACKAGES: {shipment.packages}')
    return render_template("home.html", shipment=shipment, package_num=shipment.package_num)

@views.route('/delete-package', methods=['POST'])
def delete_package():
    # request is sent as data parameter of request object (not form)
    # request.data is json string sent from index.js
    pk_object = json.loads(request.data)    # js object defined in index.js
    print(f'----------PK OBJECT FROM DELETE: {pk_object}')
    pk_id = pk_object['pk_id']
    pk = shipment.package(pk_id)    # retrieves package based on id
    pk.customer_order.remove_package(pk)
    saver.save_data(shipment)

    return jsonify({})  # jsonify empty python dictionary

@views.route('/consolidate-packages', methods=['POST'])
def consolidate():
    # request is sent as data parameter of request object (not form)
    # request.data is json string sent from index.js
    pk_ids = json.loads(request.data)    # js object defined in index.js
    print(f'-------- PK IDS FROM consolidate() IN VIEWS: {pk_ids}')
    shipment.consolidate([0, 0, 0], pk_ids, "Consolidated boxes")
    #saver.save_data(shipment)
    return jsonify({})

# VIEW/EDIT PACKAGE INFO HERE
# consignee/consignee info: name, email, phone, address
# additional info: has batteries, wants insurance
@views.route('/pkg/<string:pk_id>', methods=['GET', 'POST'])
def pk_details(pk_id):
    # pk_id is passed as a string
    package = shipment.package(pk_id)
    print(f'------PACKAGE: {package}')
    if request.method == 'POST':
        form_data = request.form
            # ASSUMES THAT SHIPPER == CUSTOMER
        if form_data['save_btn'] == 'shipper-info':
            package.customer.name = form_data['shipper_name']
            package.customer.email = form_data['shipper_email']
            package.customer.phone = form_data['shipper_phone']
            package.customer.address = form_data['shipper_address']
            package.customer.city = form_data['shipper_city']
            package.customer.state = form_data['shipper_state']
            package.customer.zip_code = form_data['shipper_zip']
        elif form_data['save_btn'] == 'consignee-info':
            package.consignee.name = form_data['consignee_name']
            package.consignee.email = form_data['consignee_email']
            package.consignee.phone = form_data['consignee_phone']
            package.consignee.address = form_data['consignee_address']
            package.consignee.city = form_data['consignee_city']
            package.consignee.state = form_data['consignee_state']
            package.consignee.zip_code = form_data['consignee_zip']
        elif form_data['save_btn'] == 'additional-info':
            package.has_batteries = 'lithium_batteries' in form_data
            package.fragile = 'is_fragile' in form_data
            package.set_dimensions(
                length=float(form_data['length']),
                width=float(form_data['width']),
                height=float(form_data['height'])
            )
            package.dim_units = form_data['units']
            package.weight = float(form_data['weight'])
            package.description = form_data['package_description']
            saver.save_data(shipment)
            return redirect(url_for('views.home'))
        else:
            raise ValueError("Do not recognize save button value, check pk_details.html")

    return render_template('pk_details.html', pk=package)

@views.route('/add-order', methods=['GET', 'POST'])
def add_order():
    global shipment
    if request.method == 'POST':
        form_data = request.form
        action = form_data.get('action')

        customer = None
        package = None
        # NOTE: 
        # default unit for weight is kg
        # delivery address == consignee address
        # fragile option doesn't do anything; need to add to shipping_objects
        if action == 'add':
            # assumes shipper = customer
            customer = Customer(
                name=form_data['shipper-name'], 
                address=form_data['shipper-address'], 
                city=form_data['shipper-city'], 
                state=form_data['shipper-state'], 
                zip_code=form_data['shipper-zip'], 
                phone=form_data['shipper-phone'], 
                email=form_data['shipper-email'])
            shipper = Shipper(
                name=form_data['shipper-name'], 
                address=form_data['shipper-address'], 
                city=form_data['shipper-city'], 
                state=form_data['shipper-state'], 
                zip_code=form_data['shipper-zip'], 
                phone=form_data['shipper-phone'], 
                email=form_data['shipper-email'])
            consignee = Consignee(
                name=form_data['consignee-name'], 
                address=form_data['consignee-address'], 
                city=form_data['consignee-city'], 
                state=form_data['consignee-state'], 
                zip_code=form_data['consignee-zip'], # returns blank string if nothing there
                phone=form_data['consignee-phone'], 
                email=form_data['consignee-email'])
            
            pickup_address = None
            if form_data.get('office-drop-off') == 'drop-off':
                office_dropoff = True
            else:
                office_dropoff = False
                pickup_address = form_data.get('pickup-address')
            # delivery address is consignee address by default
            office_pickup = form_data.get('office-pickup') == 'pick-up'
            insurance = form_data.get('insurance') == 'on' 
            order = CustomerOrder(customer, "", office_dropoff, office_pickup, insurance)
            order.assign_shipment(shipment)

            # region BOXES
            box_num = form_data.get('box-count')
            if box_num is None or int(box_num) == 0:
                error_message = "Please enter a valid number of boxes (greater than 0)."
                print("-------------------Please enter a valid number of boxes (greater than 0).")
                # FIXME error message does not work
                # do error checking from within the template instead of here
                # caused an error where site was redirecting to add order page upon submit
                # without knowing why
                return render_template('add_order.html', error=error_message)
            
            box_num = int(box_num)
            for i in range(1, box_num+1):
                dim = (float(form_data.get(f'length-{i}')),
                       float(form_data.get(f'width-{i}')),
                       float(form_data.get(f'height-{i}')))
                units = form_data.get(f'units-{i}')
                weight = float(form_data[f'weight-{i}'])
                desc = form_data[f'box-cargo-description-{i}']
                batteries = form_data.get(f'box-lithium-batteries-{i}') == 'on' 
                fragile = form_data.get(f'box-fragile-{i}') == 'on'
                pk = Package(dim, units, weight, order, shipper, consignee, desc, batteries)
                print(f"----------UNITS {units}")
            # endregion
            """
            {% if not data %}
                {% set data = {'boxes':{}} %}
            {% endif %}
            """
            print('-----------------SHIPMENT')
            print(shipment.packages)
            print(order)
            flash('Order added', category='success')
            autofill_dict = {'boxes':{}}
            
            saver.save_data(shipment)
            #return render_template('add_order.html', data=autofill_dict)
            return redirect(url_for('views.home'))
        elif action == 'cancel':
            return redirect(url_for('views.home'))
    
    blank_dict = {
        'shipper_name': '',
        'shipper_address': '',
        'shipper_city': '',
        'shipper_state': '',
        'shipper_zip': '',
        'shipper_phone': '',
        'shipper_email': '',
        'consignee_name': '',
        'consignee_address': '',
        'consignee_city': '',
        'consignee_state': '',
        'consignee_zip': '',
        'consignee_phone': '',
        'consignee_email': '',
        'office_dropoff': "",
        'office_pickup': "",
        'insurance': "",
        'box_num': "",
        'boxes': {
            'length': "",
            'width': "",
            'height': "",
            'units': '',
            'weight': "",
            'description': '',
            'batteries': "",    # make this required in the html template
            'fragile': "",
        }
    }
    autofill_dict = {
        'shipper_name': 'John Doe',
        'shipper_address': '123 street',
        'shipper_city': 'Johns city',
        'shipper_state': 'Johns state',
        'shipper_zip': 'zip code',
        'shipper_phone': '2983748932',
        'shipper_email': 'john@gmail.com',
        'consignee_name': 'somebody',
        'consignee_address': 'address',
        'consignee_city': 'sombody city',
        'consignee_state': 'somebody state',
        'consignee_zip': 'somebody zip',
        'consignee_phone': '4873983',
        'consignee_email': '',
        'office_dropoff': False,
        'office_pickup': False,
        'insurance': True,
        'box_num': 1,
        'boxes': {
            'length': 2,
            'width': 10,
            'height': 3,
            'units': 'INCH',
            'weight': 234,
            'description': 'contains items',
            'batteries': True,
            'fragile': False,
        }
    }
    
    # region chunk
    """
    if form_data['save_btn'] == 'shipper-info':
        package.shipper.name = form_data['shipper_name']
        package.shipper.email = form_data['shipper_email']
        package.shipper.phone = form_data['shipper_phone']
        package.shipper.address = form_data['shipper_address']
    elif form_data['save_btn'] == 'consignee-info':
        package.consignee.name = form_data['consignee_name']
        package.consignee.email = form_data['consignee_email']
        package.consignee.phone = form_data['consignee_phone']
        package.consignee.address = form_data['consignee_address']
    elif form_data['save_btn'] == 'additional-info':
        package.has_batteries = True if 'has_batteries' in form_data else False
        package.insurance = True if 'wants_insurance' in form_data else False
    else:
        raise ValueError("Do not recognize save button value, check pk_details.html")
    """
    # endregion
    return render_template('add_order.html', data=autofill_dict)

@views.route("/ajaxlivesearch", methods=['POST', 'GET'])
def ajaxlivesearch():
    if request.method == 'POST':
        search_word = request.form['query']
        print(search_word)
    return jsonify('success')

@views.route('/download-excel', methods=['GET'])
def download_excel():
    filename = 'exported_data.xlsx'
    file_path = os.path.join(os.path.dirname(__file__), filename)
    shipment.export_excel(file_path)
    shipment.export_excel(filename)
    return send_file(filename, as_attachment=True)


#TODO:
# find a way to view customer orders
# fix add_order pickle error
# do customer database system