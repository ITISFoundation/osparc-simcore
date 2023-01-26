/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.NewRelease", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const introText = this.tr("We are pleased to announce that some new features were deployed for you!");
      const introLabel = new qx.ui.basic.Label(introText).set({
        rich: true,
        wrap: true
      });
      this._add(introLabel);

      const reloadText = this.tr("Click on the 'Reload' button to make sure you get the latest version.");
      const reloadLabel = new qx.ui.basic.Label(reloadText).set({
        rich: true,
        wrap: true
      });
      this._add(reloadLabel);

      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const detailsText = this.tr("More details here:");
      layout.add(new qx.ui.basic.Label(detailsText));

      const link = osparc.utils.LibVersions.getVcsRefUrl();
      const linkLabel = new osparc.ui.basic.LinkLabel(this.tr("Last features"), link);
      layout.add(linkLabel, {
        flex: 1
      });

      this._add(layout, {
        flex: 1
      });

      const reloadBtn = new qx.ui.form.Button(this.tr("Reload")).set({
        appearance: "strong-button",
        alignX: "right",
        allowGrowX: false
      });
      reloadBtn.addListener("tap", () => this.__reloadButtonPressed());
      this._add(reloadBtn);
    },

    __reloadButtonPressed: function() {
      const thisCommit = osparc.utils.LibVersions.getVcsRef();
      osparc.utils.Utils.localCache.setLastCommitVcsRef(thisCommit);

      window.location.reload();
    }
  }
});
