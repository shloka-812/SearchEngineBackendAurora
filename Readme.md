I have used FastAPI and python 3.12.2.

Current approach: This strategy combines a high-speed cache system with a low-latency retrieval process for all search activity, allowing for an average response time of less than 100ms and eliminating the need to connect to an external network, which can slow down performance. All data is loaded into memory when the application is first run, through the use of the fetch_all_messages function. Since the upstream API is unreliable due to redirects, throttling, and transient errors, the fetch_all_messages function will retrieve each page sequentially (one page at a time) with a delay between requests.


Other Alternative ways:
1. Traditonal relational database with full text search:
An alternative is to persist the entire dataset in a standard database (e.g., PostgreSQL) after retrieving the data in sequential order. Data will be indexed, allowing for structured queries on the dataset. These built-in FTS capabilities can perform user searches using a single SQL query. The main advantage of this method is that it allows for more extensive datasets to be queried at scale. However, due to the added operational complexity of using a database in this manner it could be an overkill for this as the total number of records are not that much.

2. Search engine service:
We could push all the messages into search cluster like elasticsearch/opensearch and query it. It will be quite fast and scalable and perfect for long term solution but for now it can be a little costly.
 

How we can reduce the latency to 30ms?

The current approach uses simple linear search, which works well for the requirement of keeping the response time under 100ms with a dataset of 3,349 records. For 30ms, we need to reduce timecomplexity from 0(N) to ~O(logN) or ~O(1).

We can use Reverse Index, searches can be made much easier and faster by preprocessing all the messages when the server starts. A reverse index maps every unique word that appears in each message and in the usernames to a list of message IDs that contain that word (or username). Instead of searching through all messages, the system finds the IDs of the messages that contain each of the query terms, for example, "flight", intersect those lists to find matching messages and then retrieve those messages from the cache. This approach reduces the number of linear scans (O(N)) that the search algorithm must perform to find a match and replaces them with fast hash lookups and set operations, giving a level of performance that approaches constant time and easily passes the 30 ms barrier.



