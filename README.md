# Nestora AI Agent

An AI-powered customer-support assistant for a demo online store called
**Nestora**. The project combines a FastAPI backend, a
LangChain/LangGraph tool-calling workflow, Supabase for authentication
and transactional data, Pinecone for support-document retrieval, and
LangSmith for observability.

> **Project status:** In development. The backend is being built and
> tested first with Postman. A React customer storefront and admin
> dashboard are planned. Do not assume every listed feature is complete
> until it has been implemented and tested in the current repository.

## Features and goals

The intended application will let customers:

-   Ask questions about product manuals, FAQs, and refund/return
    policies.
-   Search the live product catalog and check current prices and stock.
-   Place orders after explicitly confirming the product, quantity,
    price, and total.
-   View their own orders and order details.
-   Cancel orders when the order status permits cancellation.
-   Use an AI chat interface that calls backend tools instead of
    inventing product or order information.

The planned admin experience will support protected product management
and stock updates.

## Technology stack

  -----------------------------------------------------------------------
  Component                           Purpose
  ----------------------------------- -----------------------------------
  Python                              Backend language

  FastAPI                             REST API

  Supabase Auth                       User authentication

  Supabase Postgres                   Products, orders, order items, and
                                      inventory movements

  LangChain                           LLM integration and tools

  LangGraph                           Agent workflow and tool routing

  OpenAI                              Chat model and embeddings

  Pinecone                            Vector storage and retrieval for
                                      support documents

  LangSmith                           Tracing and debugging

  Postman                             API testing

  React (planned)                     Customer storefront and admin
                                      dashboard
  -----------------------------------------------------------------------

The project has previously used `gpt-4o-mini` for chat and
`text-embedding-3-small` for embeddings. Confirm the current
configuration and package versions in the repository before changing
them.

## Architecture overview

``` text
Customer / Admin
       |
       v
 FastAPI API
       |
       +---- Supabase Auth / verified user identity
       |
       v
 LangGraph chat workflow
       |
       +---- Product search tool --------> Supabase products
       |
       +---- Order tools ----------------> Supabase RPCs / order tables
       |
       +---- Support-document search ----> Pinecone
       |
       +---- OpenAI chat model
       |
       v
 Customer response

LangSmith can trace the model and tool workflow when configured.
```

**Source of truth matters:** - Use Supabase for current product prices,
stock, and order data. - Use Pinecone/RAG for information in support
documents, such as product manuals and return policies. - Derive
customer identity from verified authentication, not from model-generated
arguments. - Database functions should validate and perform stock/order
mutations atomically.

## Project structure

The structure below is the intended layout; verify it against the actual
repository.

``` text
AI-Agent/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── permissions.py
│   ├── db/
│   │   └── config.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   ├── products.py
│   │   └── orders.py
│   └── ai/
│       ├── llm.py
│       ├── prompts.py
│       ├── tools.py
│       ├── graph.py
│       ├── retriever.py
│       ├── ingest.py
│       └── evaluate_rag.py
├── Documents/
│   ├── Nestora_FAQs.pdf
│   ├── Nestora_Brew_Smart_Kettle_NK-500_Manual.pdf
│   └── Nestora_Refund_and_Return_Policy.pdf
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Requirements

-   Python 3.11 (the version used during development)
-   `uv` for Python environment and dependency management
-   A Supabase project
-   An OpenAI API key
-   A Pinecone account/index
-   A LangSmith API key if tracing is needed
-   Postman for API testing

The frontend is planned and may require Node.js/npm once development
begins.

## Setup

### 1. Clone or open the repository

``` bash
git clone <your-repository-url>
cd AI-Agent
```

If you already have the project locally, open its root directory
instead.

### 2. Create and sync the environment

If the repository uses `uv` and `pyproject.toml`:

``` bash
uv sync
```

If the environment has not yet been initialized and the repository does
not have a `uv` environment, follow the existing project setup rather
than creating a second environment unnecessarily.

### 3. Configure environment variables

Create a local `.env` file using `.env.example` as a template. Use the
exact names required by `app/core/config.py`.

Typical variable names include:

``` dotenv
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_JWKS_URL=
OPENAI_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX_NAME=
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=AI-Agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
ADMIN_USER_IDS=
```

Do not commit the real `.env` file. Never put service-role keys or AI
provider keys in a frontend application or public repository.
`SUPABASE_SECRET_KEY` is server-only and must be kept private.

`ADMIN_USER_IDS` should contain the UUID(s) of authorized administrator
accounts, separated by commas, if the current authorization
implementation uses this setting.

### 4. Configure Supabase

The database should contain the tables and policies required by the
actual API implementation. The intended data model includes:

-   `products`
-   `orders`
-   `order_items`
-   `inventory_movements`

The project has also used database RPC functions for stock updates,
order placement, and order cancellation. Inspect the SQL definitions and
grants in your Supabase project; this README does not automatically
create the database schema.

Ensure that: - Row Level Security is enabled and policies restrict
customer data correctly. - Admin operations are authorized on the
server. - Order placement and cancellation perform related database
changes atomically. - The backend uses the correct Supabase URL and
keys.

### 5. Configure Pinecone and support documents

Create/configure a Pinecone index compatible with the selected embedding
model. Check the index dimension and the embedding model before
ingestion.

Support documents previously used:

-   `Documents/Nestora_FAQs.pdf`
-   `Documents/Nestora_Brew_Smart_Kettle_NK-500_Manual.pdf`
-   `Documents/Nestora_Refund_and_Return_Policy.pdf`

Place the files in the expected directory and use the ingestion
module/command implemented in the current repository. Verify the actual
module before running it; for example, if the file is
`app/ai/ingest.py`, the command may be:

``` bash
uv run python -m app.ai.ingest
```

The command above is valid only if that module provides a runnable entry
point.

## Run the API

From the project root:

``` bash
uv run uvicorn app.main:app --reload
```

Open the FastAPI documentation in your local browser:

-   Swagger UI: `http://127.0.0.1:8000/docs`
-   OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

These are the default local addresses when Uvicorn runs on port 8000. If
you configure a different host or port, use that address instead.

## API routes

The following routes have been discussed during development. Confirm
them in the current FastAPI OpenAPI docs and router files before relying
on them.

  ------------------------------------------------------------------------------------------
  Method                  Route                                      Purpose
  ----------------------- ------------------------------------------ -----------------------
  `POST`                  `/api/chat/`                               Send a message to the
                                                                     AI assistant

  `GET`                   `/api/products`                            List active products

  `GET`                   `/api/products/{product_id}`               Get product details

  `POST`                  `/api/admin/products`                      Create a product
                                                                     (admin)

  `PATCH`                 `/api/admin/products/{product_id}`         Update a product
                                                                     (admin)

  `POST`                  `/api/admin/products/{product_id}/stock`   Add stock (admin)

  `POST`                  `/api/orders`                              Place an order

  `GET`                   `/api/orders`                              List the authenticated
                                                                     customer's orders

  `GET`                   `/api/orders/{order_number}`               Get an owned order

  `POST`                  `/api/orders/{order_number}/cancel`        Cancel an eligible
                                                                     order
  ------------------------------------------------------------------------------------------

Authentication and request bodies depend on the implementation. Use the
OpenAPI docs as the authoritative source for the current API contract.

## Order flow and important implementation rules

1.  Search the live catalog using `search_products`.
2.  Use the real `product_id` UUID returned by Supabase, not a SKU or
    placeholder.
3.  Show the customer the product, unit price, quantity, and total.
4.  Obtain explicit customer confirmation.
5.  Place the order through the backend/database function.
6.  Verify the returned order and inventory changes.

Example RPC item format:

``` json
[
  {
    "product_id": "REAL_UUID_RETURNED_BY_PRODUCT_SEARCH",
    "quantity": 1
  }
]
```

The UUID text above is a placeholder for documentation and must be
replaced with a real UUID at runtime. The backend should validate the
UUID, quantity, current stock, and current price. Do not trust prices or
totals generated by the LLM.

A successful HTTP response from the chat endpoint does not by itself
prove that an order was placed. Verify the tool result and database
records.

## Testing with Postman

Recommended testing order:

1.  Start the FastAPI server.
2.  Authenticate and obtain a valid access token using the configured
    auth flow.
3.  Test product listing and product search.
4.  Ask a support question answered by one of the documents.
5.  Test a product stock/price question and verify the live Supabase
    data.
6.  Test order placement with a real product UUID, confirming before
    submission.
7.  Verify the order, order items, stock reduction, and inventory
    movement in Supabase.
8.  Test order history and order details with the correct user.
9.  Test cancellation for an eligible order and verify stock is restored
    once.
10. Test invalid tokens, insufficient stock, invalid UUIDs, missing
    products, non-admin access, and attempts to access another
    customer's orders.

Do not mark a test as passed until it has been executed and the result
verified.

## Security notes

-   Keep `.env` out of source control.
-   Do not expose Supabase service-role, OpenAI, Pinecone, or LangSmith
    secrets.
-   Enforce permissions in the backend; frontend button hiding is not
    security.
-   Scope customer order queries by the authenticated user.
-   Do not let the LLM choose a customer `user_id`.
-   Never let the LLM determine authoritative product prices, stock, or
    order totals.
-   Validate all tool inputs and handle tool failures without falsely
    claiming success.
-   Avoid logging tokens, secrets, or unnecessary personal data.

## Planned frontend

The planned React application will have:

### Customer storefront

-   Product catalog and product details
-   Search and current pricing/stock
-   Supabase sign-up/sign-in
-   Shopping cart and order confirmation
-   AI support chat
-   Order history, order details, and cancellation where allowed
-   Loading, empty, error, and success states

### Admin dashboard

-   Admin-only access
-   Product creation and editing
-   Stock management
-   Relevant order/inventory visibility as scope is finalized

The frontend is a planned milestone and should not be described as
complete until implemented and tested against the backend.

## Troubleshooting notes

### `invalid input syntax for type uuid`

The order RPC expects a real product UUID. Do not pass values like
`"ACTUAL_SUPABASE_UUID"` or a SKU such as `SB-001`. Copy the
`product_id` from the latest `search_products` result.

### The AI does not call the expected tool

Check that the tool is bound to the model in `app/ai/llm.py`. A tool
existing in the graph's execution map does not automatically mean the
model can call it. Inspect the bound tool names and the actual tool-call
arguments.

### The API returns HTTP 200 but the action failed

A chat endpoint can return HTTP 200 while returning a natural-language
tool error. Inspect server logs with secrets removed, the tool result,
and the database state.

### No RAG results

Check that the ingestion process discovered the files, that embeddings
succeeded, that the Pinecone index dimension is correct, and that
metadata filters match the stored metadata.

### OpenAI authentication errors

A revoked or invalid key may cause authentication failures. Replace it
through the provider's secure dashboard, update `.env`, and restart the
server. Never paste the key into logs or source control.

## Project status and roadmap

-   [ ] Verify environment setup and all configuration.
-   [ ] Verify authentication and admin permissions.
-   [ ] Verify all intended LangGraph tools are bound and correctly
    scoped.
-   [ ] Verify product search against live Supabase data.
-   [ ] Verify document ingestion, retrieval, and source grounding.
-   [ ] Verify order creation, totals, stock changes, and inventory
    movements.
-   [ ] Verify order ownership and cancellation rules.
-   [ ] Complete backend tests and document results.
-   [ ] Build the React customer storefront.
-   [ ] Build the React admin dashboard.
-   [ ] Test customer and admin flows end to end.
-   [ ] Document deployment and operational steps.

## Contributing / working with Claude Code

See [`CLAUDE.md`](./CLAUDE.md) for project-specific development context
and working rules.

When changing the code: 1. Inspect the existing implementation first. 2.
Make a small, focused change. 3. Explain why it is needed. 4. Run the
relevant tests. 5. Record what passed and what remains unverified.

Do not claim the project is complete until the backend, frontend,
security boundaries, and end-to-end flows have been implemented and
tested.
