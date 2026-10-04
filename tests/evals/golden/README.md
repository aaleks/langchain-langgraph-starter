# Golden evaluation data -- written by a human, never by an agent

Each `*.jsonl` file here is the ground truth for one `evaluated` requirement:
one case per line, a stable `id`, and a `source` saying where the case came from.

The edit guard refuses an agent's write to this directory. That is the point:
the failure mode of eval-driven work is "the eval failed, so adjust the expected
answer", which lowers the bar and leaves the suite green. An agent may propose
cases; a person writes them here.

Below about 20 cases a threshold measures the sampler, not the system. Report N
beside every score.
