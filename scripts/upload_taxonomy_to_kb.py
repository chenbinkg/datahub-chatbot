#!/usr/bin/env python3
"""
Upload taxonomy data to Bedrock Knowledge Base for GraphRAG
"""
import json
import boto3
import os
from pathlib import Path

def convert_taxonomy_to_documents(json_file_path: str) -> list:
    """Convert taxonomy JSON to document format for knowledge base"""
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        taxonomy_data = json.load(f)
    
    documents = []
    
    for lineage_name, lineage_list in taxonomy_data.items():
        # Create a document for each taxonomic lineage
        lineage_text = f"Taxonomic lineage: {lineage_name}\n\n"
        
        for entry in lineage_list:
            for name, details in entry.items():
                rank = details.get("rank", "Unknown")
                aphia_id = details.get("AphiaID", "")
                
                lineage_text += f"- {name} (Rank: {rank}"
                if aphia_id:
                    lineage_text += f", AphiaID: {aphia_id}"
                lineage_text += ")\n"
        
        # Add relationships
        lineage_text += "\nTaxonomic relationships:\n"
        prev_name = None
        for entry in lineage_list:
            for name, details in entry.items():
                if prev_name:
                    lineage_text += f"- {prev_name} belongs to {name}\n"
                prev_name = name
        
        documents.append({
            'content': lineage_text,
            'metadata': {
                'lineage': lineage_name,
                'type': 'taxonomy',
                'source': 'biigle_label_tree'
            }
        })
    
    return documents

def upload_to_s3(documents: list, bucket_name: str):
    """Upload documents to S3 bucket"""
    
    s3_client = boto3.client('s3')
    
    for i, doc in enumerate(documents):
        # Create text file for each document
        filename = f"taxonomy_lineage_{i+1}.txt"
        
        # Upload document content
        s3_client.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=doc['content'],
            ContentType='text/plain',
            Metadata=doc['metadata']
        )
        
        print(f"Uploaded {filename} to s3://{bucket_name}/")

def start_ingestion(knowledge_base_id: str, data_source_id: str):
    """Start knowledge base ingestion job"""
    
    bedrock_client = boto3.client('bedrock-agent')
    
    response = bedrock_client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id
    )
    
    job_id = response['ingestionJob']['ingestionJobId']
    print(f"Started ingestion job: {job_id}")
    return job_id

def main():
    # Get parameters from SSM
    ssm_client = boto3.client('ssm')
    
    try:
        kb_id = ssm_client.get_parameter(Name='/remote-mcp-server/knowledge-base-id')['Parameter']['Value']
        s3_bucket = ssm_client.get_parameter(Name='/remote-mcp-server/knowledge-base-s3-bucket')['Parameter']['Value']
    except Exception as e:
        print(f"Error getting SSM parameters: {e}")
        print("Make sure to deploy the Neptune Analytics infrastructure first")
        return
    
    # Convert taxonomy data
    json_file = Path(__file__).parent.parent / "dtis_ontology" / "biigle_label_tree_filled_rank.json"
    
    if not json_file.exists():
        print(f"Taxonomy file not found: {json_file}")
        return
    
    print("Converting taxonomy data to documents...")
    documents = convert_taxonomy_to_documents(str(json_file))
    print(f"Created {len(documents)} documents")
    
    # Upload to S3
    print(f"Uploading to S3 bucket: {s3_bucket}")
    upload_to_s3(documents, s3_bucket)
    
    # Get data source ID
    bedrock_client = boto3.client('bedrock-agent')
    data_sources = bedrock_client.list_data_sources(knowledgeBaseId=kb_id)
    
    if data_sources['dataSourceSummaries']:
        data_source_id = data_sources['dataSourceSummaries'][0]['dataSourceId']
        
        # Start ingestion
        print("Starting knowledge base ingestion...")
        job_id = start_ingestion(kb_id, data_source_id)
        print(f"Ingestion job started with ID: {job_id}")
        print("Monitor the job status in AWS Console or use AWS CLI:")
        print(f"aws bedrock-agent get-ingestion-job --knowledge-base-id {kb_id} --data-source-id {data_source_id} --ingestion-job-id {job_id}")
    else:
        print("No data sources found for knowledge base")

if __name__ == "__main__":
    main()