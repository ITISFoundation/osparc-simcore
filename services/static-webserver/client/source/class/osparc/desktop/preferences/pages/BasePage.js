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
      spacing: 10,
      alignX: "center"
    }));

    // Page title
    this.add(new qx.ui.basic.Label(title).set({
      font: "title-16"
    }));

    // spacer
    this.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
    this.set({
      backgroundColor: "background-main-2",
      paddingLeft: 10
    });
  },

  members: {
    /**
     * Common layout of secion's box
     * @param {page section's name} sectionName
     */
    _createSectionBox: function(sectionName) {
      let box = new qx.ui.groupbox.GroupBox(sectionName);
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
      let label = new qx.ui.basic.Label().set({
        value: message,
        rich: true,
        font: "text-12"
      });
      return label;
    }
  }
});
