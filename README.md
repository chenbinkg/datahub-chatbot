# Data Platform Remote MCP Server

Remote MCP Server for Data Platform project with GraphRAG taxonomy knowledge base.

## Features

- **MongoDB MCP Server**: Query DTIS observation data
- **GraphRAG Knowledge Base**: Taxonomy knowledge using Neptune Analytics
- **Bedrock Agent**: AI assistant with tool access and knowledge base integration
- **Gradio UI**: Web interface for chatbot interaction

## Git repository structure

- [infra](infra/) - contains Terraform code that manages AWS resources (e.g. Amazon S3 buckets)
- [scripts](scripts/) - contains scripts
- [notebooks](notebooks/) - contains jupyter notebooks for testing
- [dtis_ontology](dtis_ontology/) - contains DTIS taxonomy data for knowledge base