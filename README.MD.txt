# This project is supposed to be a research project that builds an agentic system to self improve or evolve an existing database into a more powerful database (think latency, speed, efficiency) based on a given workload, etc. 


## For evaluation

- start with duckdb and then try to pick one workload (TPC-DS/H); supply the query through template for generalization. Train validation test/ in schema (easy to trast) 60-70 for traing 10-20 val 20 for test. Multiple query per template, separating by template easy for generatlzation
- In our case we can try to evolve duckdub to make newer versions of duckdb. 
- We need to make sure we dont overfit or reverse engineer or hardcode solutions and try to make a generic framework. 
- Idea is to produce improvement versions of duckdb (For starters upto 3 versions) where it might be that v1 might work better for some use case and we can plot out a graph to show how with more versions we are able to reduce time (If it works)
- For eval we would probably need to build duckdb everytime. 


## For resources
- Go through the docs folder to see existing solutions. Intentlab is really good and we should try to produce something along those lines (Link to intentlab: https://intentlab.ai/blog/an-agent-fleet-on-clickbench)
- For architecture, we could start with a simple foundation that would make sense (Refer VibeServe paper to gather understanding of architecture)
- Jetstream and Bespoke are also good papers to get a good understanding.
- We can produce an architecture, plan.md and framework and then test using opus 5.5


