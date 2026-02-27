"""Human-in-the-loop review tool — pauses the agent and asks the user to
approve or modify the proposed simulation parameters."""


def request_user_review(parameters_summary: str) -> str:
    """Present the proposed simulation parameters to the user for review.

    Call this after deciding parameters in Phase 1 and before executing
    the simulation pipeline. The parameters_summary should be a readable
    table of all chosen parameter values with brief justifications.

    The user can:
      - approve the parameters (reply "yes" or "ok")
      - request modifications (reply with specific changes)
      - ask to see a geometry visualization first

    Returns the user's response as a string.
    """
    print("\n" + "=" * 64)
    print("  SIMULATION PARAMETERS — REVIEW REQUIRED")
    print("=" * 64)
    print(parameters_summary)
    print("=" * 64)
    print("\nOptions:")
    print("  - Type 'yes' or 'ok' to approve and run the simulation")
    print("  - Type 'viz' to see a 3D geometry visualization first")
    print("  - Or describe any changes you'd like to make")
    print()

    response = input("Your response: ").strip()
    return response
