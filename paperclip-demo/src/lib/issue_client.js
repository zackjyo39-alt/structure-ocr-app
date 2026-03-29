// Issue client for Paperclip runtime
// This module provides a way to interact with Paperclip runtime services

class IssueClient {
  /**
   * List issues from the Paperclip runtime
   * @param {Object} context - The execution context with tool_call capability
   * @param {string} assignee - The assignee to filter issues by
   * @returns {Promise<Array>} List of issues
   */
  async listIssues(context, assignee) {
    // In the Paperclip runtime, we use the issueService to list issues
    // We make a tool call to the runtime's issueService.list method
    try {
      // Call the Paperclip runtime's issue service to list issues
      // The exact format of the tool_call may vary based on the runtime implementation
      // For now, we'll use a common pattern and adjust as needed
      const response = await context.tool_call('issueService', 'list', {
        companyId: context.companyId,
        filter: assignee ? { assigneeUserId: assignee } : {}
      });
      
      // Extract issues from response
      const issues = response.issues || [];
      return issues;
    } catch (error) {
      console.error('Error listing issues:', error);
      // Return empty array on error to maintain consistency
      return [];
    }
  }
  
  /**
   * Update issue status
   * @param {Object} context - The execution context
   * @param {string} issueId - The ID of the issue to update
   * @param {string} status - The new status
   * @returns {Promise<boolean>} True if successful
   */
  async updateIssueStatus(context, issueId, status) {
    try {
      const response = await context.tool_call('issueService', 'update', {
        issueId: issueId,
        data: { status: status }
      });
      return response.success;
    } catch (error) {
      console.error('Error updating issue status:', error);
      return false;
    }
  }
  
  /**
   * Post comment to an issue
   * @param {Object} context - The execution context
   * @param {string} issueId - The ID of the issue
   * @param {string} text - The comment text
   * @returns {Promise<boolean>} True if successful
   */
  async postComment(context, issueId, text) {
    try {
      const response = await context.tool_call('issueService', 'addComment', {
        issueId: issueId,
        body: text
      });
      return response.success;
    } catch (error) {
      console.error('Error posting comment:', error);
      return false;
    }
  }
}

module.exports = { IssueClient };