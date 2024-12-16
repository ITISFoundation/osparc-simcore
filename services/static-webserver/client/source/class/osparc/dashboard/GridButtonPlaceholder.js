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

qx.Class.define("osparc.dashboard.GridButtonPlaceholder", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.PLACEHOLDER);

    this.set({
      cursor: "not-allowed"
    });

    this.getChildControl("footer").exclude();
  },

  properties: {
    task: {
      check: "osparc.data.PollTask",
      init: null,
      nullable: true,
      apply: "__applyTask"
    }
  },

  statics: {
    POS: {
      STATE: {
        row: 5,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      },
      PROGRESS: {
        row: 6,
        column: 0,
        rowSpan: 1,
        colSpan: 4
      }
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      let layout;
      switch (id) {
        case "state-label": {
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            allowGrowX: true,
            allowShrinkX: true,
            rich: true,
            anonymous: true,
            font: "text-12",
            allowGrowY: true,
            wrap: true
          });
          layout = this.getChildControl("body");
          layout.addAt(control, 0);
          break;
        }
        case "progress-bar": {
          layout = this.getChildControl("title-row");
          control = new qx.ui.indicator.ProgressBar().set({
            maxHeight: 6,
            alignX: "center",
            alignY: "middle",
            allowGrowY: false,
            allowGrowX: true,
            margin: 0,
          });
          control.getChildControl("progress").set({
            backgroundColor: "strong-main"
          });
          layout.addAt(control, 1);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    buildLayout: function(titleText, icon, stateText, showProgressBar = false) {
      const title = this.getChildControl("title");
      if (titleText) {
        title.setValue(titleText);
      }
      if (icon) {
        this.setIcon(icon);
      }

      const stateLabel = this.getChildControl("state-label");
      if (stateText) {
        stateLabel.setValue(stateText);
      }

      this.getChildControl("progress-bar").set({
        visibility: showProgressBar ? "visible" : "excluded"
      });
    },

    getBlocked: function() {
      return true;
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getChildControl("title").getValue().toString()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length === 0) {
          return true;
        }
      }
      return false;
    },

    __applyTask: function(task) {
      task.addListener("updateReceived", e => {
        const updateData = e.getData();
        if ("task_progress" in updateData) {
          const progress = updateData["task_progress"];
          this.getChildControl("progress-bar").set({
            value: progress["percent"]*100
          });
          this.getChildControl("state-label").set({
            value: progress["message"]
          });
        }
      }, this);
    }
  }
});
