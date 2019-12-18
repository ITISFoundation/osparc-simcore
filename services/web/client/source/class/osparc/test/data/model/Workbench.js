/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Test Workbench class
 *
 */
qx.Class.define("osparc.test.data.model.Workbench",
  {
    extend: qx.dev.unit.TestCase,
    include: [qx.dev.unit.MRequirements, qx.dev.unit.MMock],

    members:
    {
      setUp: function() {
        console.debug("Setting up .. ");
        this.debug("Setting up ...");

        // ToDo OM: Tobi is this correct?
        osparc.data.Permissions.getInstance().setRole("user");

        const studyData = {
          name: "Test Study",
          description: ""
        };
        const study = new osparc.data.model.Study(studyData);
        const wbData = {};
        this.__workbench = new osparc.data.model.Workbench(study, wbData);
      },

      tearDown: function() {
        console.debug("Tear down .. ");
        this.debug("Tear down ...");
        this.getSandbox().restore();
      },

      createDummyNode() {
        const key = null;
        const version = null;
        const uuid = null;
        const parent = null;
        return this.__workbench.createNode(key, version, uuid, parent);
      },

      /*
      ---------------------- -----------------------------------------------------
        TESTS
      ---------------------------------------------------------------------------
      */

      testDuplicatedNodeConnections: function() {
        const edgeId = null;
        const node1 = this.createDummyNode();
        const node2 = this.createDummyNode();
        const edge1 = this.__workbench.createEdge(edgeId, node1.getNodeId(), node2.getNodeId());
        const edge2 = this.__workbench.createEdge(edgeId, node1.getNodeId(), node2.getNodeId());
        this.assertIdentical(edge1.getEdgeId(), edge2.getEdgeId(), "Both edges must be the same");
      },

      testUniqueName: function() {
        const node1 = this.createDummyNode();
        const node2 = this.createDummyNode();
        this.assertNotIdentical(node1.getLabel(), node2.getLabel(), "Labels must be different");
      }
    }
  });
