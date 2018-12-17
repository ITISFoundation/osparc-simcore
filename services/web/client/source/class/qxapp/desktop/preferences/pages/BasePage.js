/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.desktop.preferences.pages.BasePage", {
  extend: qx.ui.tabview.Page,

  construct: function(title, iconSrc = null) {
    this.base(arguments, null, iconSrc);

    this.setLayout(new qx.ui.layout.VBox(10).set({
      spacing: 10,
      alignX: "center"
    }));

    // title
    this.add(new qx.ui.basic.Label(title + " Settings").set({
      font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-16"])
    }));

    // spacer
    this.add(new qx.ui.core.Spacer(null, 10)); // TODO add decorator?
  },

  members: {

    /** Common layout of secion's box
     *
     * @param {page section's name} sectionName
     */
    _createSectionBox: function(sectionName) {
      let box = new qx.ui.groupbox.GroupBox(sectionName);
      box.setLayout(new qx.ui.layout.VBox(10));

      return box;
    },

    /** Common layout for and font for tooltip label
     *
     */
    _createHelpLabel: function(message=null) {
      let label = new qx.ui.basic.Label().set({
        value: message,
        rich : true,
        font : qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-12"])
      });
      return label;
    }
  }
});
