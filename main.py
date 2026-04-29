from src.agent.aml_agent import AMLAgent

def main():
    # 1. Initialize the agent
    agent = AMLAgent()

    try:
        # 2. Run setup (Idempotent: creates collection, uploads MCP, registers tools)
        print("Starting setup...")
        agent.setup()

        # 3. Run a query
        print("Running investigation...")
        query = """
        Investigate BLAIRMORE HOLDINGS, INC. for AML risk.
        Use AML Guard Tool and MCP Tool Runner tool.
        """
        
        response = agent.run(query)
        
        print(f"Investigation Result: {response}")

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()