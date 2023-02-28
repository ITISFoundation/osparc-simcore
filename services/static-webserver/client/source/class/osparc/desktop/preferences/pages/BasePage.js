/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.desktop.preferences.pages.BasePage", {
  extend: qx.ui.tabview.Page,

  construct: function(title, iconSrc = null) {
    this.base(arguments, null, iconSrc);

    this.setLayout(new qx.ui.layout.VBox(10).set({
      spacing: 5,
      alignX: "center"
    }));

    // Page title
    this.add(new qx.ui.basic.Label(title).set({
      font: "text-14",
      alignX: "left"
    }));
    // spacer
    this.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
    this.set({
      backgroundColor: "background-main-2",
      paddingTop: 10,
      paddingLeft: 20
    });
  },

  members: {
    /**
     * Common layout of section's box
     * @param {page section's name} sectionName
     */
    _createSectionBox: function(sectionName) {
      const box = new qx.ui.groupbox.GroupBox(sectionName);
      box.getChildControl("legend").set({
        font: "text-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      box.setLayout(new qx.ui.layout.VBox(10));
      return box;
    },

    /**
     * Common layout for tooltip label
     */
    _createHelpLabel: function(message=null) {
      const label = new qx.ui.basic.Label().set({
        value: message,
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return label;
    }
  }
});
