# Intake

- **Class:** structural
- **Intent:** For the owner, the product's point: the assistant may propose
  to add, close or reassign a task, and nothing is written until the owner
  approves.
  - **The pause:** the run stops with LangChain's approval request, and the
    owner resumes it on the same thread -- approve or reject, one decision per
    write -- through the local server's API.
  - **Approve:** the write is applied once (4b1's store), and the model
    goes on.
  - **Reject:** nothing is written, and the run ends without another model
    call.
- **Because:** it adds an interrupt, two nodes and three tools to the
  registered graph. It changes the state schema (version 2) and the prompt
  (version 2), and it makes the first payload a client must understand. Each
  is an interface of the server's threads.
- **Approved:** the owner, on 2026-10-14:
  - "Server API, LangChain format (Recommended)";
  - "Run ends, no more model calls (Recommended)";
  - "Approve or reject (Recommended)".

  The split of 4b into the store (4b1, #12) and this route was decided by
  the agent under the owner's standing delegation.

## Scope, against the roadmap's slice 4b2

All of it:
- the three write tools;
- the pause in LangChain's format;
- a rejection that ends the run;
- the key from the thread, the reply and the call;
- the prompt;
- the approval through the local server, end to end.

Carried in from 4b1's verify:
- tools are given a reader, never the store (finding 4);
- a write node must not repeat its effect on a continue.

## Ratchet

| When | From | To | Because |
|---|---|---|---|

## Spike

N-A
