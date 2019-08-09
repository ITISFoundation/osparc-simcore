/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Test Permissions
 *
 */
qx.Class.define("qxapp.test.data.Permissions", {
  extend: qx.dev.unit.TestCase,
  include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

  members: {
    __workbench: null,

    setUp: function() {
      console.debug("Setting up .. ");
      this.debug("Setting up ...");
    },

    tearDown: function() {
      console.debug("Tear down .. ");
      this.debug("Tear down ...");
      this.getSandbox().restore();
    },

    createEmptyWorkbench: function() {
      const studyData = {
        name: "Test Study",
        description: ""
      };
      const study = new qxapp.data.model.Study(studyData);
      const wbData = {};
      this.__workbench = new qxapp.data.model.Workbench(study, wbData);
    },

    createDummyNode: function() {
      const key = null;
      const version = null;
      const uuid = null;
      const parent = null;
      const populateNodeData = true;
      return this.__workbench.createNode(key, version, uuid, parent, populateNodeData);
    },

    /*
    ---------------------- -----------------------------------------------------
      TESTS
    ---------------------------------------------------------------------------
    */

    // test study.node.create
    testStudyNodeCreate: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("guest");
      const anonNode = this.createDummyNode();
      this.assertNull(anonNode, "guest is not allowed to create nodes");

      qxapp.data.Permissions.getInstance().setRole("user");
      const userNode = this.createDummyNode();
      this.assertNotNull(userNode, "user is allowed to create nodes");
    },

    // test study.node.delete
    testStudyNodeDelete: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("user");
      const dummyNode = this.createDummyNode();
      this.assertNotNull(dummyNode, "user is allowed to create nodes");

      qxapp.data.Permissions.getInstance().setRole("guest");
      let removed = this.__workbench.removeNode(dummyNode.getNodeId());
      this.assertFalse(removed, "guest is not allowed to delete nodes");

      qxapp.data.Permissions.getInstance().setRole("user");
      removed = this.__workbench.removeNode(dummyNode.getNodeId());
      this.assertTrue(removed, "user is allowed to delete nodes");
    },

    // test study.node.rename
    testStudyNodeRename: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("user");
      const node = this.createDummyNode();
      const newLabel = "my new label";

      qxapp.data.Permissions.getInstance().setRole("guest");
      node.renameNode(newLabel);
      this.assertNotIdentical(node.getLabel(), newLabel, "guest is not allowed to rename nodes");

      qxapp.data.Permissions.getInstance().setRole("user");
      node.renameNode(newLabel);
      this.assertIdentical(node.getLabel(), newLabel, "guest is not allowed to rename nodes");
    },

    // test study.edge.create
    testStudyEdgeCreate: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("user");
      const node1 = this.createDummyNode();
      const node2 = this.createDummyNode();

      qxapp.data.Permissions.getInstance().setRole("guest");
      const anonEdge = this.__workbench.createEdge(null, node1.getNodeId(), node2.getNodeId());
      this.assertNull(anonEdge, "guest is not allowed to create edges");

      qxapp.data.Permissions.getInstance().setRole("user");
      const userEdge = this.__workbench.createEdge(null, node1.getNodeId(), node2.getNodeId());
      this.assertNotNull(userEdge, "user is allowed to create edges");
    },

    // test study.edge.delete
    testStudyEdgeDelete: function() {
      this.createEmptyWorkbench();

      qxapp.data.Permissions.getInstance().setRole("user");
      const node1 = this.createDummyNode();
      const node2 = this.createDummyNode();
      const edge = this.__workbench.createEdge(null, node1.getNodeId(), node2.getNodeId());

      qxapp.data.Permissions.getInstance().setRole("guest");
      let removed = this.__workbench.removeEdge(edge.getEdgeId());
      this.assertFalse(removed, "guest is not allowed to delete edges");

      qxapp.data.Permissions.getInstance().setRole("user");
      removed = this.__workbench.removeEdge(edge.getEdgeId());
      this.assertTrue(removed, "user is allowed to delete edges");
    },

    // test study.node.data.push
    testStudyNodeDataPush: function() {
      const loc0 = "loc0";
      const file0 = "file0";
      const loc1 = "loc1";
      const file1 = "file1";
      const store = qxapp.data.Store.getInstance();

      qxapp.data.Permissions.getInstance().setRole("guest");
      const req0sent = store.copyFile(loc0, file0, loc1, file1);
      this.assertFalse(req0sent, "guest is not allowed to push files");

      qxapp.data.Permissions.getInstance().setRole("user");
      const req1sent = store.copyFile(loc0, file0, loc1, file1);
      this.assertTrue(req1sent, "user is allowed to push files");
    },

    // test study.node.data.delete
    testStudyNodeDataDelete: function() {
      const loc0 = "loc0";
      const file0 = "file0";
      const store = qxapp.data.Store.getInstance();

      qxapp.data.Permissions.getInstance().setRole("guest");
      const req0sent = store.deleteFile(loc0, file0);
      this.assertFalse(req0sent, "guest is not allowed to delete files");

      qxapp.data.Permissions.getInstance().setRole("user");
      const req1sent = store.deleteFile(loc0, file0);
      this.assertTrue(req1sent, "user is allowed to delete files");
    }
  }
});
