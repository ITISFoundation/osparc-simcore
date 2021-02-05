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

qx.Class.define("osparc.dashboard.StudyBrowserButtonPlaceholder", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.set({
      cursor: "not-allowed"
    });
  },

  statics: {
    POS: {
      STATE: osparc.dashboard.StudyBrowserButtonBase.THUMBNAIL + 1,
      PROGRESS: osparc.dashboard.StudyBrowserButtonBase.THUMBNAIL + 2
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "state-label":
          control = new qx.ui.basic.Label();
          this._mainLayout.addAt(control, this.self().POS.STATE);
          break;
        case "progress-bar":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10
          });
          this._mainLayout.addAt(control, this.self().POS.PROGRESS);
          break;
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

      this._getChildren().forEach(item => {
        item.setOpacity(0.4);
      });
    },

    isLocked: function() {
      return true;
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
