# Order Management Service

The Order Management Service handles the processing and management of orders within the OStore application. It enables customers to place orders, tracks order status, manages order details, and calculates the total amount for each order. Additionally, it maintains associations between orders and the products included in each order through order items. The service facilitates order fulfillment by coordinating with other components, such as the [Product Catalog Service](/userport/pcs-design), to ensure accurate inventory management and timely delivery to customers.

## Data Model

### Orders
Each order represents a purchase made by a customer.

Attributes include:

1. **orderID (Primary Key):** Unique identifier for the order.
2. **userID (Foreign Key):** Identifier for the user who placed the order.
3. **orderDate:** Date and time when the order was placed.
4. **status:** Current status of the order (e.g., pending, confirmed, shipped, delivered).
5. **totalAmount:** Total amount of the order.

Each order can have multiple order items associated with it.

### Order Items
Order items represent individual products within an order.

Attributes include:

1. **orderItemID (Primary Key):** Unique identifier for the order item.
2. **orderID (Foreign Key):** Identifier for the order to which the item belongs.
3. **productID (Foreign Key):** Identifier for the product being ordered.
quantity: Quantity of the product ordered.
4. **price:** Price of the product at the time of the order.

### Schema
```
CREATE TABLE Orders (
    orderID SERIAL PRIMARY KEY,
    userID INT NOT NULL,
    orderDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    totalAmount DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (userID) REFERENCES Users(userID)
);

CREATE TABLE OrderItems (
    orderItemID SERIAL PRIMARY KEY,
    orderID INT NOT NULL,
    productID INT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (orderID) REFERENCES Orders(orderID),
    FOREIGN KEY (productID) REFERENCES Products(productID)
);
```

In this schema:
1. The **Orders** table stores information about each order, including the user who placed the order, the order date, status, and total amount.
2. The **OrderItems** table contains details about each product within an order, such as the order to which it belongs, the product being ordered, the quantity, and the price at the time of the order.
3. Foreign key constraints ensure referential integrity between the Orders and OrderItems tables and their respective related tables (e.g., **Users**, **Products**).

This data model allows the Order Management Service to efficiently manage orders and associated order items, facilitating order processing, tracking, and reporting within the OStore application.

## API Endpoints

### Create Order
**Endpoint:** `POST /orders`

**Description:** Allows customers to create a new order.

**Request Body:**
```
     {
       "userID": “ID of the user”,
       "orderItems": [
         {
           "productID": “ID of the specific product”,
           "quantity": “quantity of the product”
         },
         {
           "productID": “ID of the specific product”,
           "quantity": “quantity of the product”
         }
       ]
     }
```

**Response Body (Success)**
```
{
       "orderID": "ID of the order",
       "orderDate": "Date that order is placed",
       "status": "status of created order",
       "totalAmount": "Total amount that the order costs",
       "shipmentID": "ID of the shipment"
}
```


**Response Body (Error):**
```
     {
       "error": "Error string associated with failed order creation"
     }
```

**Notes**

1. The request body contains the user ID and an array of order items, each specifying the product ID and quantity.
2. If the order is successfully created, the response includes the order ID, order date, status, and total amount.
3. If any of the requested products have insufficient quantity, an error response is returned with details of the unavailable product(s).

The Create order API implementation checks by calling the Product Catalog Service if there are enough quainties for each product item that the user has placed in the order. If not, it returns an error and the order does not get placed.

If there are sufficient quantities for each order item, then it calls the Shipment Tracking Service to create a shipment and then returns the created order (with all the relevant details) back to the user.

### Get Order Details
**Endpoint:** `GET /orders/{orderID}`

**Description:** Retrieves details of a specific order.

**Request Body:** (No request body required)

**Response Body (Success):**
```
     {
       "orderID": “ID of the order”,
       "userID": “ID of the user”,
       "orderDate": "Date when order was created",
       "status": "current status of the order",
       "totalAmount": “total amount that the order costs”,
       "orderItems": [
         {
           "orderItemID": “ID of the order item”,
           "productID": “ID of the product”,
           "quantity": “Quantity of the product ordered”,
           "price": “Price of the product”
         },
         {
           "orderItemID": “ID of the order item”,
           "productID": “ID of the product”,
           "quantity": “Quantity of the product ordered”,
           "price": “Price of the product”
         },
       ]
     }
```

**Response Body (Error):**
```
     {
       "error": "Error message associated with failed Order fetch"
     }
```

**Notes**
1. The endpoint retrieves details of the specified order, including order ID, user ID, order date, status, total amount, and order items.
2. If the order ID provided does not exist, an error response is returned indicating that the order was not found.


### Update Order

This is not an API endpoint but actually a Kafka Consumer thread that listens to order shipment updates provided by the Shipment Tracking System. The Shipment Tracking system acts as a Kafka producer and publishes a TrackingEvent which is consumed by the Order Management Service. This leads to:
1. An update to the status of the Order in the database.
2. A user notification event is produced to Kafka which is then consumed by the User Notification Service which ultimately notifies the customer.

## Authentication

In the Order Management System, authentication ensures that only authorized users can access endpoints and perform actions related to order management. Here's how authentication can be implemented in more detail:

**Endpoint:** `POST /auth/login`

**Description:** Allows customers to authenticate using their credentials (e.g., username and password).

**Request Body:**
```
 {
       "email": "email of the customer",
       "password": "password of the customer"
 }
```

**Response:** 

Upon successful authentication, the server generates a JSON Web Token (JWT) and returns it in the response body. The JWT typically contains the user's ID or other relevant information.
```
{
       "token": "JWT Token string"
}
```


### Protected Endpoints
Endpoints related to order management (e.g., creating, or retrieving orders) are protected and require a valid JWT token in the Authorization header for access.

Example of protected endpoint:

**Endpoint:** `POST /orders`

**Authorization Header:** 
```
       Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```


### Token Verification
1. Each protected endpoint validates the JWT token provided in the Authorization header. If the token is missing or invalid, the server responds with a 401 Unauthorized error.
2. The server verifies the signature of the JWT token and checks if it hasn't expired.

### Token Refresh
 The JWT tokens have expiration times, so a token refresh mechanism can be implemented to generate new tokens without requiring users to log in again.

**Endpoint:** `POST /auth/refresh`

**Request Body:**
```
{
         "token": "existing JWT token"
}
```


### Logout
A logout endpoint can be provided to invalidate JWT tokens on the client side.

**Endpoint:** `POST /auth/logout`

**Request Body:** (No request body required)

**Response:** Upon successful logout, the server will respond with a 200 OK status.

By implementing authentication, the Order Management System ensures that only authenticated customers have access to sensitive endpoints and data related to order management, enhancing security and data integrity within the system.
