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

    this.setLayout(new qx.ui.layout.VBox(20).set({
      spacing: 5,
      alignX: "center"
    }));

    this.getChildControl("title").set({
      value: title
    });

    // spacer
    this.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
    this.set({
      backgroundColor: "background-main-2",
      paddingTop: 5,
      paddingLeft: 15
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title": {
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignX: "left"
          });
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    showLabelOnTab: function() {
      const title = this.getChildControl("title").getValue();
      const tabButton = this.getChildControl("button");
      tabButton.set({
        label: title,
        font: "text-14"
      });
      // eslint-disable-next-line no-underscore-dangle
      const buttonLayout = tabButton._getLayout();
      buttonLayout.setColumnAlign(0, "center", "middle"); // center icon
      buttonLayout.setColumnWidth(0, 24); // align texts
      buttonLayout.setSpacingX(5);
    },

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
