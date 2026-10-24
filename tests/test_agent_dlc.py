import unittest
from prubeth.agents.lifecycle import AgentLifecycleManager, AgentLifecycleState

class TestAgentDLC(unittest.TestCase):
    """Agent Development Life Cycle (Agent-DLC): Runtime Lifecycle & Reflection Verification."""

    def test_agent_lifecycle_standard_flow(self):
        """Agent-DLC: Test standard progression from Inception to Retirement."""
        mgr = AgentLifecycleManager(agent_id="subagent-coder-1", role="coder")
        self.assertEqual(mgr.current_state, AgentLifecycleState.INCEPTION)

        mgr.transition_stage(AgentLifecycleState.CONTEXT_GROUNDING, "Ingesting repository AST context")
        self.assertEqual(mgr.current_state, AgentLifecycleState.CONTEXT_GROUNDING)

        mgr.transition_stage(AgentLifecycleState.PLAN_SYNTHESIS, "Formulating diff sequence")
        self.assertEqual(mgr.current_state, AgentLifecycleState.PLAN_SYNTHESIS)

        mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH, "Writing changes into shadow worktree")
        self.assertEqual(mgr.current_state, AgentLifecycleState.TOOL_DISPATCH)
        self.assertEqual(mgr.iterations, 1)

        mgr.transition_stage(AgentLifecycleState.REFLECTION_CRITIQUE, "Adversarial critic review")
        self.assertEqual(mgr.current_state, AgentLifecycleState.REFLECTION_CRITIQUE)
        self.assertEqual(mgr.critic_reviews, 1)

        mgr.transition_stage(AgentLifecycleState.RETIREMENT, "Worktree merged to root")
        self.assertEqual(mgr.current_state, AgentLifecycleState.RETIREMENT)

        mgr.transition_stage(AgentLifecycleState.TERMINATED, "Subagent resources deallocated")
        self.assertEqual(mgr.current_state, AgentLifecycleState.TERMINATED)

        summary = mgr.get_summary()
        self.assertTrue(summary["is_retired"])
        self.assertEqual(summary["iterations"], 1)
        self.assertEqual(summary["critic_reviews"], 1)

    def test_agent_lifecycle_illegal_transition_rejection(self):
        """Agent-DLC: Attempting to bypass context grounding directly to dispatch raises error."""
        mgr = AgentLifecycleManager(agent_id="subagent-critic-1", role="critic")
        with self.assertRaises(ValueError):
            mgr.transition_stage(AgentLifecycleState.TOOL_DISPATCH)

if __name__ == "__main__":
    unittest.main()
