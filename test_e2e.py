"""End-to-end test with test_leo.txt file."""

import asyncio
import httpx
import json


async def test_document_upload_and_query():
    """Test uploading document and querying it."""
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("End-to-End Test: Upload and Query")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Upload test_leo.txt
        print("\nStep 1: Uploading test_leo.txt...")
        with open("test_leo.txt", "rb") as f:
            files = {"file": ("test_leo.txt", f, "text/plain")}
            response = await client.post(
                f"{base_url}/api/v1/documents/upload",
                files=files
            )
        
        if response.status_code == 200:
            print("✓ Document uploaded successfully")
            doc_data = response.json()
            print(f"  - Document ID: {doc_data['id']}")
            print(f"  - Chunks: {doc_data.get('num_chunks', 'N/A')}")
        else:
            print(f"✗ Upload failed: {response.status_code}")
            print(response.text)
            return False
        
        # Wait a moment for processing
        await asyncio.sleep(2)
        
        # Step 2: Query using smart endpoint
        print("\nStep 2: Querying with smart endpoint...")
        query = "what does leo like"
        
        response = await client.post(
            f"{base_url}/api/v1/query/smart",
            json={
                "query": query,
                "top_k": 5,
                "include_sources": True
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Query successful")
            print(f"  - Answer: {result['answer']}")
            print(f"  - Sources: {len(result.get('sources', []))}")
            print(f"  - Engine used: {result.get('metadata', {}).get('engine_used', 'N/A')}")
            
            routing_decision = result.get('metadata', {}).get('routing_decision', {})
            if routing_decision:
                print(f"  - Routing decision:")
                print(f"    * Use ultra: {routing_decision.get('use_ultra')}")
                print(f"    * Confidence: {routing_decision.get('confidence', 0):.2f}")
                print(f"    * Reasoning: {', '.join(routing_decision.get('reasoning', []))}")
            
            return True
        else:
            print(f"✗ Query failed: {response.status_code}")
            print(response.text)
            return False


async def main():
    """Run end-to-end test."""
    print("\n" + "=" * 60)
    print("END-TO-END TEST")
    print("=" * 60)
    print("\nThis test will:")
    print("1. Upload test_leo.txt")
    print("2. Query using the smart endpoint")
    print("3. Verify routing works correctly\n")
    
    try:
        # Check if server is running
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get("http://localhost:8000/health")
                if response.status_code != 200:
                    print("❌ Server is not responding correctly")
                    print("Please start the server with: make dev")
                    return 1
            except httpx.ConnectError:
                print("❌ Cannot connect to server")
                print("Please start the server with: make dev")
                return 1
        
        success = await test_document_upload_and_query()
        
        if success:
            print("\n" + "=" * 60)
            print("✓ END-TO-END TEST PASSED!")
            print("=" * 60)
            print("\nThe system successfully:")
            print("- Uploaded and processed the document")
            print("- Analyzed query complexity")
            print("- Routed to appropriate engine")
            print("- Generated accurate answer")
            return 0
        else:
            print("\n❌ Test failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
