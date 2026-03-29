const { IssueClient } = require('./issue_client');

describe('IssueClient', () => {
  let client;
  let mockContext;

  beforeEach(() => {
    client = new IssueClient();
    mockContext = {
      companyId: 'test-company-id',
      tool_call: jest.fn()
    };
  });

  describe('listIssues', () => {
    it('should return empty array by default', async () => {
      const issues = await client.listIssues(mockContext, 'principal_architect');
      expect(issues).toEqual([]);
      expect(mockContext.tool_call).not.toHaveBeenCalled();
    });
  });

  describe('updateIssueStatus', () => {
    it('should return false by default', async () => {
      const result = await client.updateIssueStatus(mockContext, 'issue-1', 'In Progress');
      expect(result).toBe(false);
      expect(mockContext.tool_call).not.toHaveBeenCalled();
    });
  });

  describe('postComment', () => {
    it('should return false by default', async () => {
      const result = await client.postComment(mockContext, 'issue-1', 'Test comment');
      expect(result).toBe(false);
      expect(mockContext.tool_call).not.toHaveBeenCalled();
    });
  });
});