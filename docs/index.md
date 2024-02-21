# OStore Order Placement Flow Design

OStore is an e-commerce website that sells all categories of products over the internet. This document explains the high level design of the order placement journey on the backend.

## Components

The system consists of the following components (servers).

1. **Frontend Service:** Provides a user interface for browsing products, managing shopping cart and placing orders.

2. [**Order Management Service:**](/userport/oms-design) Facilitates order processing, including order placement, payment processing, and order fulfillment.

3. [**Product Catalog Service:**](/userport/pcs-design) Manages the inventory of products, including CRUD operations for products and categories.

4. [**Shipment Tracking Service:**](/userport/sts-design) Creates shipments for orders and manages the tracking of shipments.

5. **User Notification Service:** Responsible for communicating with users over email or text messages. This service provides updates to users about their order statuses.

6. [**Apache Kafka:**](https://kafka.apache.org/) Message Broker responsible for managing the event bus that decouples (using producer and consumers) communication between multiple services in the system. 

All these components have separate binaries in production. Unlike traditional microservices design, all these components use the same **PostgreSQL** database to perform CRUD operations. That means each Service can access and update the database tables independently. We chose this approach because it is simpler given our current scale to not have to maintain multiple databases in production. As the website scales, we might migrate to a full microservices based system with each service maintaining its own database.

All the components above (including the Postgres database and Kafka brokers) are deployed on **AWS (Amazon Web Services)** in production.

System Architecture diagram: ![OStore System Architecture](/ostore-system-arch.jpg)

## Order placement flow

Here are the steps in the order placement flow:

1. The customer arrives at the OStore website on their browser and that triggers a request to the Frontend Service.

2. The Frontend Service returns the web page where the user can search and look up details of different products under various categories. The user can select different products and add them to their cart.

3. When they are ready, they place the order on the website.

4. The frontend client receives the order request and forwards it to the order management service.

5. The Order Management Service (OMS) receives the order details and calls the Product Catalog Service (PCS) to check if there is enough quantity for each product in the cart.

6. If there isn’t enough stock, then the Order Management Service (OMS) returns an error to the frontend server which in turns returns an error to the browser prompting the user to remove it from the cart.

7. If there is enough stock, then the OMS calls the Shipment Tracking Service (STS) to create a shipment.

8. The Shipment Tracking Services (STS) creates a shipment with one of the carriers and returns the confirmation quickly to the OMS. At the same time, a queue job is enqueued by the Shipment Tracking Service to complete shipment processing. Once that processing is complete, another periodic queue job is created to track the shipment until it is delivered.

9. During shipment tracking, if the status of the order changes, the Shipment Tracking service produces an event to Kafka which is then consumed by the Order Management System. The OMS updates the User Notification Service which then sends the update to the user via an email or text message.

Please refer to the other documents linked above to learn more detailed information.
