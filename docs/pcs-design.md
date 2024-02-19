# Product Catalog Service

The Product Catalog Service manages the inventory of products in the OStore Application. It provides endpoints for creating, updating, and deleting products, as well as retrieving product details and listing products. Additionally, it ensures the availability of products by verifying quantities upon order placement and adjusts stock levels accordingly. This service also interacts with other components, such as the Order Management Service, to facilitate order processing and maintain inventory accuracy.

## Data Model

The Product Catalog Service will utilize a relational database like Postgres MongoDB for storing product information. This allows enforcing ACID properties and referential integrity between tables.

1. Each product entry will contain attributes such as product ID, name, description, price, category ID, and quantity in stock.
2. Additionally, indexes will be created on commonly queried fields (e.g., product name, category) to improve query performance.

### Product

1. **productID (Primary Key):** Unique identifier for the product.
2. **name:** Name of the product.
3. **description:** Description of the product.
4. **price:** Price of the product.
5. **categoryID (Foreign Key):** Identifier for the category to which the product belongs.
6. **quantity:** Quantity of the product available in stock.

### Category
1. **categoryID (Primary Key):** Unique identifier for the category.
2. **name:** Name of the category.

Here's how you can represent this data model in SQL:
```
CREATE TABLE Category (
    categoryID SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE Product (
    productID SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    categoryID INT,
    quantity INT NOT NULL,
    FOREIGN KEY (categoryID) REFERENCES Category(categoryID)
);
```

With this data model, each product belongs to a specific category, allowing for easy organization and navigation within the product catalog. The quantity attribute tracks the availability of each product in stock, ensuring accurate inventory management.

### Secondary indices
For the Product table:
1. An index on the categoryID column could improve the performance of queries that filter or join on this field.
2. An index on the price column could speed up queries involving sorting or filtering by price.

For the Category table:
1. Since the categoryID is the primary key, it already has a unique index created automatically. However, if there are additional fields that are frequently queried, such as the name, we could create an index on the name column.

```
-- Add secondary indices to the Product table
CREATE INDEX idx_product_category_id ON Product (categoryID);
CREATE INDEX idx_product_price ON Product (price);

-- Add secondary index to the Category table
CREATE INDEX idx_category_name ON Category (name);
```


These indices will help improve the performance of queries that involve filtering, sorting, or joining on the indexed columns. However, it's important to carefully consider the trade-offs, as indices can increase storage overhead and impact write performance during data modification operations.

### Concurrency and Consistency
Database transactions will be used to maintain data integrity and consistency when performing multiple operations within a single request or across multiple concurrent requests.

## API Endpoints

### Create Product
**Endpoint:** `POST /products`

**Description:** Allows administrators to add new products to the catalog. Not accessible to customers.

**Request Body:**
```
     {
       "name": "Name of the product",
       "description": "Description of the product",
       "price": “Price of the product”,
       "categoryID": “Category of the product”,
       "quantity": “Number of products to add to the stock”
     }
```

**Response:** 
```
{
      “productID”: “ID of the created Product.”
}
```

### Update Product
**Endpoint:** `PUT /products/{productID}`

**Description:** Enables administrators to modify existing product details. Not accessible to customers.

**Request Body:** 
List of fields to be updated and their respective values.
```
{
       "name": "Name to update",
       "description": "Update to description",
       "price": “Price update”,
       "categoryID": “Category update”,
       "quantity": “Quantity update”
}
```

The fields are optional, so any field not specified in the request body will not be updated.

### Delete Product
**Endpoint:** `DELETE /products/{productID}`

**Description:** Allows administrators to remove products from the catalog. Not accessible to customers.

**Request Body:** (No request body required)

**Response:**
```
{
    "productD": "ID of deleted product"
}
```

### Get Product Details
**Endpoint:** `GET /products/{productID}`

**Description:** Retrieves detailed information about a specific product.
**Response Body (Success)**
```
{  
  "productID": "ID of the product",
  "name": "Name of the product",
  "brand": "Brand of the product",
  "description": "Description of the product",
  "price": "Price of the product",
  "quantityAvailable": "Quantity of the product",
  "category": "Category of the product",
  "imageUrl": "Link to product image"
}
```

### List Products
**Endpoint:** `GET /products`

**Description:** Returns a list of products available in the catalog according to the filter specified in the request.

**Request Body**
Contains filters for the products to be listed. The filters can be on any of the attributes of a given product like ID, category ID, price etc.

Example request body for filtering by categoryID:
```
{
     "categoryID": 1
}
```

Example request body for filtering by price range:  
 ```
 {
     "minPrice": 50,
     "maxPrice": 100
 }
```

## Authentication and Authorization
To implement authentication in the Product Catalog Service, we'll use JSON Web Tokens (JWT) for secure authentication and authorization. Administrators will need to authenticate themselves using their credentials before they can perform any actions on the product catalog, such as creating, updating, or deleting products. Here's how we can incorporate authentication into the service:

### Authentication
**Endpoint:** `POST /auth/login`

**Description:** Allows administrators to authenticate using their username and password.

**Request Body:**
```
{
       "username": "admin@example.com",
       "password": "admin123"
}
```

**Response:** Upon successful authentication, the server will return a JWT token in the response body, which the administrator can use to authenticate subsequent requests.

### Authorization Middleware
A middleware function will be implemented to verify the JWT token sent by the client with each request to protected endpoints.
If the token is valid, the request will be allowed to proceed. Otherwise, the server will respond with a 401 Unauthorized error.

### Protected Endpoints
Endpoints that require authentication and authorization, such as creating, updating, or deleting products, will be protected.
Before processing requests to these endpoints, the server will verify the JWT token provided in the request headers.

### Token Refresh
**Endpoint:** `POST /auth/refresh`

**Description:** Allows administrators to refresh their JWT token before it expires.

Request Body:
```
 {
    "token": "existing JWT token"
 }
```


**Response:** Upon successful token refresh, the server will return a new JWT token in the response body.

### Logout
**Endpoint:** `POST /auth/logout`

**Description:** Allows administrators to invalidate their JWT token and log out.

**Request Body:** (No request body required)

**Response:** Upon successful logout, the server may respond with a 200 OK status.

### Error Handling
* Proper error handling will be implemented to handle cases where authentication fails or tokens are invalid or expired.
* Error responses will include appropriate status codes and error messages to communicate the reason for the failure.

By implementing authentication using JWT tokens, we ensure that only authenticated administrators have access to the Product Catalog Service endpoints, thereby enhancing the security of the system. The use of JWT tokens also eliminates the need for server-side session management, making the system more scalable and stateless.
