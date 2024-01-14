# Slack Channel and Threads Creation

This wiki explains the architecture of channel and thread creation on the Slack backend. It does not explain DM creation which has a separate flow.

## What is a Channel?

Slack organizes conversations into dedicated spaces called channels. Channels bring order and clarity to work - you can create them for any project, topic, or team. With the right people and information in one place, teams can share ideas, make decisions, and move work forward.

## What is a Thread?

Threads help you create organized discussions around specific messages. They let you discuss a topic in more detail without adding clutter to a channel or direct message (DM) conversation.

## What are the different flows?

Channels and threads can be created by 2 separate flows on the frontend:

1. **Users from the Slack UI**: Only members of a Slack Workspace can create channels or threads inside it.
2. **API calls from Slack App**: Only registered apps in a given Slack Workspace can call the backend to create channels or threads.

Both flows call the same API on the backend to create the channel or thread.

## Technical details

On the backend, both thread and channel creation flows are largely the same barring a few differences.

However the flow is different for different types of requests received on the backend:
1. **Users from Slack UI creating a Restricted channel or any Thread**: Asynchronous flow. These are roughly 99% of the requests.
2. **Users from Slack UI creating a Discoverable channel**: Synchronous flow. These are roughly 0.5% of the requests.
3. **API calls from Slack App**: Synchronous flow. These are roughly 0.5% of the requests.

### What is the synchronous flow?
In the synchronous flow when the backend receives a request, the following RPC calls happen in sequence:
1. Call to Slack Memberships Service to create a Membership entity.
2. Call to Slack Memberships Service to update the entity (created in the previous step) with the requested (channel or thread) memberships.
3. Call to RPC Slack Storage Service to create the Membership entity and requested memberships.

The Slack Memberships Service RPC calls are synchronous in nature with the RPC returning only after [1] the membership entity is created and [2] memberships are updated respectively. Further since the calls are sequential, this results in an overall higher latency for the backend flow.

Overall Latency of this flow is around 1.8s at 50 percentile and 2.4s at 99 percentile.

### What is the asynchronous flow? 
In the asynchronous flow when the backend receives a request, the following RPC calls happen in sequence:
1. Call to Slack Memberships Asynchronous Service to create a Membership entity and requested memberships.
2. Call to RPC Slack Storage Service to create the Membership entity and requested memberships.

The Slack Memberships Asynchronous Service RPC call is asynchronous in nature. As a result, the RPC does not wait for the Membership entity or requested memberships to be fully created before returning. As a result, the latency for this API is much lower resulting in an overall lower latency for the backend flow.

The tradeoff is that while the Memberships Asynchronous Service is still processing the Membership entity creation and update, newer requests to update or delete the same Membership entity cannot be processed and will be rejected. The SLO for the Memberships Asynchronous Service is less than 500ms for 99% of requests. Since this latency is not too large it is expected that in most cases users in Slack UI won’t really think of adding or removing memberships by the time the asynchronous service finishes processing. 

Additionally, the core capability of sending messages is unaffected by asynchronous or synchronous flows so users can immediately start chatting once the channel or thread is created in both flows.  

Overall Latency of this flow is around 0.9s at 50 percentile and 1.4s at 99 percentile.
