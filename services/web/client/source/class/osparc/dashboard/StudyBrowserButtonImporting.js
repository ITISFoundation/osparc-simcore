/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Class.define("osparc.dashboard.StudyBrowserButtonImporting", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();

    this.addListener("changeValue", this.__itemSelected, this);
  },

  members: {
    __stateLabel: null,
    __porgressBar: null,

    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Importing Study..."));

      this.setIcon("@FontAwesome5Solid/file-import/70");

      const stateLabel = this.__stateLabel = new qx.ui.basic.Label();
      this._mainLayout.add(stateLabel);

      const progressBar = this.__porgressBar = new qx.ui.indicator.ProgressBar().set({
        height: 10
      });
      this._mainLayout.add(progressBar);

      this.set({
        cursor: "not-allowed"
      });

      this._getChildren().forEach(item => {
        item.setOpacity(0.4);
      });
    },

    setStateLabel: function(stateLabel) {
      return this.__stateLabel.setValue(stateLabel);
    },

    getProgressBar: function() {
      return this.__porgressBar;
    },

    isLocked: function() {
      return true;
    },

    __itemSelected: function() {
      console.log("Do you want to cancel the task");
      this.setValue(false);
    },

    _onToggleChange: function() {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getChildControl("title").getValue().toString()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      return false;
    }
  }
});
