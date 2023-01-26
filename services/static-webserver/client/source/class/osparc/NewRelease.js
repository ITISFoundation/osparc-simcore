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

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const text = this.tr("We are pleased to announce that some new features have been deployed for you!");
      const label1 = new qx.ui.basic.Label(text).set({
        rich: true,
        wrap: true
      });
      this._add(label1, {
        flex: 1
      });

      const text2 = this.tr("More details here:");
      this._add(new qx.ui.basic.Label(text2));

      const link = osparc.utils.LibVersions.getVcsRefUrl();
      this._add(new osparc.ui.basic.LinkLabel(this.tr("Last features"), link));

      const reloadBtn = new qx.ui.form.Button(this.tr("Reload")).set({
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
