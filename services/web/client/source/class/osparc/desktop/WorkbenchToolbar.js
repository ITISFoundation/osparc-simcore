/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.WorkbenchToolbar", {
  extend: osparc.desktop.Toolbar,

  construct: function() {
    this.base(arguments);

    this.__attachEventHandlers();
  },

  members: {
    // overriden
    _buildLayout: function() {
      this.getChildControl("breadcrumb-navigation");
      this._startStopBtns = this.getChildControl("start-stop-btns");
    },

    // overriden
    _populateGuidedNodesLayout: function() {
      const study = this.getStudy();
      if (study) {
        const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
        this._navNodes.populateButtons(nodeIds, "slash");
      }
    },

    __workbenchSelectionChanged: function(msg) {
      const selectedNodes = msg.getData();
      this.getStartStopButtons().nodeSelectionChanged(selectedNodes);
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeWorkbenchSelection", this.__workbenchSelectionChanged, this);
    }
  }
});
