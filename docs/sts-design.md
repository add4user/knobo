# Shipment Tracking Service
The Shipment Tracking Service manages creation of shipment for each order and continuously monitors the status of the shipments in the OStore application. It interfaces with shipping carriers to retrieve real-time tracking information for each package in transit.

## Data Model

### Shipments
Represents the overall shipment of an order. The attributes include a unique shipment ID, order ID (to link to the corresponding order), shipping address, shipment status, and other relevant information. One order can have multiple shipments if the items are shipped separately or if there are partial shipments.

### Packages
Represents individual packages within a shipment. Attributes include a unique package ID, shipment ID (to link to the corresponding shipment), package dimensions, weight, package status, and other package-specific details.

### Carriers
Represents shipping carriers or logistics providers responsible for transporting the packages. Attributes include a unique carrier ID, carrier name, contact information, and other carrier-specific details.

### Tracking Events
Represents events related to the tracking of packages. Attributes include a unique tracking event ID, package ID (to link to the corresponding package), event type (e.g., “shipped”, “in transit”, “out for delivery”, “delivered”), event timestamp, location (if available), and any additional event-specific details.

Here's how you can represent this data model in SQL:
```
CREATE TABLE Shipments (
    shipmentID SERIAL PRIMARY KEY,
    orderID INT NOT NULL,
    shippingAddress TEXT NOT NULL,
    shipmentStatus VARCHAR(50) NOT NULL,
);

CREATE TABLE Packages (
    packageID SERIAL PRIMARY KEY,
    shipmentID INT NOT NULL,
    packageDimensions TEXT,
    packageWeight DECIMAL(10, 2),
    packageStatus VARCHAR(50) NOT NULL,
);

CREATE TABLE Carriers (
    carrierID SERIAL PRIMARY KEY,
    carrierName VARCHAR(100) NOT NULL,
    contactInformation TEXT,
);

CREATE TABLE TrackingEvents (
    trackingEventID SERIAL PRIMARY KEY,
    packageID INT NOT NULL,
    eventType VARCHAR(50) NOT NULL,
    eventTimestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    location TEXT,
);
```

In this data model:
1. The **Shipments** table stores information about each shipment, including the order it belongs to and its current status.
2. The **Packages** table contains details about individual packages within each shipment, such as package dimensions, weight, and status.
3. The **Carriers** table stores information about shipping carriers or logistics providers.
4. The **TrackingEvents** table records events related to package tracking, including event type, timestamp, location, and any additional details.

This data model enables the tracking system to efficiently manage and track shipments and packages, providing real-time updates on their status and location throughout the shipping process.


## API Endpoints

### Create Shipment
**Endpoint:** `POST /shipments`

**Description:** Allows users to create a new shipment.

**Request Body:**
```
     {
       "orderID": 123,
       "shippingAddress": "123 Main St, City, Country",
       "shipmentStatus": "pending"
     }
```

**Response Body (Success)**
```
     {
       "shipmentID": 1001,
       "orderID": 123,
       "shippingAddress": "123 Main St, City, Country",
       "shipmentStatus": "pending"
     }
```

**Response Body (Error)**
```
     {
       "error": "Invalid shipping address"
     }
```

**Notes**
1. The request body contains information such as the order ID, shipping address, and initial shipment status.
2. If the shipment is successfully created, the server responds with details of the newly created shipment, including the shipment ID, order ID, shipping address, and shipment status. If there are any errors, such as an invalid shipping address, an appropriate error message is returned.

### Get Shipment Details
**Endpoint:** `GET /shipments/{shipmentID}``
**Description:** Retrieves details of a specific shipment.
**Request Parameters:** The shipment ID parameter specifies the ID of the shipment whose details are to be retrieved.
**Response Body (Success):**
```
{
       "shipmentID": 1001,
       "orderID": 123,
       "shippingAddress": "123 Main St, City, Country",
       "shipmentStatus": "shipped"
 }
```


**Response Body (Error):**
```
     {
       "error": "Shipment not found"
     }
```

**Notes:**

Upon successful retrieval, the server responds with details of the specified shipment, including the shipment ID, order ID, shipping address, and shipment status. If the requested shipment ID does not exist, an appropriate error message is returned.

These endpoints provide essential functionalities for managing and tracking shipments within the system, enabling users to create shipments, and retrieve shipment details. They facilitate effective shipment tracking and management, ensuring transparency and efficiency throughout the shipping process.

## Carrier Integration Layer
The integration layer interfaces with different shipping carriers to execute the shipping process. It acts as a bridge between the Shipment API and the various shipping carrier APIs or services. 

This layer abstracts the complexities of interacting with multiple carriers and provides a unified interface for the Shipment API to initiate shipping operations. It is implemented in the Shipment Service binary itself and makes outgoing calls to respective carrier APIs to create shipment and manage shipments.

The implementation is asynchronous in nature so that the Shipment API can return quickly without waiting on long running shipment tasks.

### Integration Modules
The integration layer defines a standardized interface or set of functions that the Shipment API handler can call to interact with different carrier integration modules.

This interface abstracts the specific details of each carrier's API, providing a consistent way for the Shipment API to initiate shipping tasks regardless of the carrier being used.

Currently we support only 2 carriers:
1. Fedex
2. USPS

Each integration module is responsible for communicating with the respective carrier's API or service to perform shipping-related operations, such as creating shipments, generating labels, and tracking packages.

#### Shipping Operations
The integration layer supports various modules that perform different shipping operations, including:
1. **Creating shipments:** This module is responsible for generating shipping labels, specifying package dimensions and weights, and selecting shipping methods. When an order is placed by a user, this module is called and it creates a Shipment entry in the database and returns the ID. The rest of the work in generating shipment labels, specifying packages and selecting shipping methods is performed in a background task in an asynchronous manner.
2. **Tracking shipments:** Querying tracking information and status updates for packages in transit. For each order, there is one periodic task that keeps track of the shipment only on a daily basis. Whenever there is an update in the shipment status (for example, “out for delivery” to “delivered”), it is responsible for creating a TrackingEvent (defined in the schema above) and publishing it to Kafka broker as a producer. This event is then subscribed to by the Order Management Service (which acts as the consumer) which then notifies the customer about the order status.

#### Authentication and Configuration
The integration layer handles authentication with each shipping carrier's API, managing API keys, authentication tokens, or other credentials required for access.

It also allows for the configuration of shipping preferences, such as default shipping options, carrier preferences, and shipping account details.

### Fault Tolerance and Alerting
If there are any errors in the processing, the requests are retried on the same task queues with exponential backoff between consecutive retries until it finally succeeds. In some cases these are internal errors that need to be triaged by the oncall team. So if the messages in the queues have not been successfully acknowledged over 1 day, then the system alerts the primary oncaller of the team.

