Use zeromq for delivery:

- have 2 channesl one for sending one for receiving
- use default prots
- queues for accumulating
- check out some time series data strucuture or how to implemtn soemthing easily manageble? OrderDict would be a basic example? I don't know, we need to fill it up with scertain indexes but serching is a hassle, we need to keep an index for fast query and data extraction from it

Client SIDE:
- api for setting a value (at time?)
- api for asking to record a value
- api for fetching a value at time (if the value does not exist raise an error)

Server SIDE:
- queues for accumulating data (should put a limit and raise an error if they are filled up) it will fail when inserting data in them

Supported data:
- we provide: str, int, float, bytes, all other stuff must be serialized to and from bytes
- messagepack will be providing serialization and will be able to allow us to expand the usage
-
