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

      const detailsText = this.tr("What's new");
      const link = osparc.utils.LibVersions.getVcsRefUrl();
      const linkLabel = new osparc.ui.basic.LinkLabel(detailsText, link);
      this._add(linkLabel, {
        flex: 1
      });

      const reloadText = this.tr("Click on the 'Reload' button to make sure you get the latest version.");
      const reloadLabel = new qx.ui.basic.Label(reloadText).set({
        rich: true,
        wrap: true
      });
      this._add(reloadLabel);

      const reloadBtn = new qx.ui.form.Button(this.tr("Reload")).set({
        appearance: "strong-button",
        alignX: "right",
        allowGrowX: false
      });
      reloadBtn.addListener("tap", () => this.__reloadButtonPressed());
      this._add(reloadBtn);
    },

    __saveCommitVcsRef: function() {
      const thisCommit = osparc.utils.LibVersions.getVcsRef();
      osparc.utils.Utils.localCache.setLastCommitVcsRef(thisCommit);
    },

    __reloadButtonPressed: function() {
      this.__saveCommitVcsRef();

      // OM todo: hard refresh
      window.location.reload();
    }
  }
});
