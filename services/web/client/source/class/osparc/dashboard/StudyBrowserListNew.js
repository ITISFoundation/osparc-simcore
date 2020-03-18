/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.StudyBrowserListNew", {
  extend: osparc.dashboard.StudyBrowserListBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "studyDescription":
          control = new qx.ui.basic.Label(this.tr("Start with a empty study")).set({
            rich: true,
            allowGrowY: false,
            anonymous: true
          });
          this._mainLayout.addAt(control, 1);
          break;
        case "icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/plus-circle/64").set({
            anonymous: true,
            scale: true,
            allowStretchX: true,
            allowStretchY: true,
            alignY: "middle",
            height: 145
          });
          this._mainLayout.addAt(control, 2);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.setStudyTitle(this.tr("Create New Study"));
      this.getChildControl("studyDescription");
      let icon = this.getChildControl("icon");
      icon.set({
        paddingTop: icon.getSource() && icon.getSource().match(/^@/) ? 30 : 0
      });
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
