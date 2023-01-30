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

qx.Class.define("osparc.AboutProduct", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About Product"));

    osparc.store.StaticInfo.getInstance().getDisplayName()
      .then(displayName => {
        this.setCaption(this.tr("About ") + displayName);
      });

    this.set({
      layout: new qx.ui.layout.VBox(5),
      maxWidth: this.self().MAX_WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });

    this.__buildLayout();
  },

  statics: {
    MAX_WIDTH: 400,
    PADDING: 15
  },

  members: {
    __buildLayout: function() {
      const introText = new qx.ui.basic.Label().set({
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(introText);
      osparc.store.StaticInfo.getInstance().getDisplayName()
        .then(displayName => {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const aboutText = this.tr(` 
          is powered by the <a href='https://github.com/ITISFoundation/osparc-simcore' style='color: ${color}' target='_blank'>o2S2PARC platform</a> 
          for online-accessible, cloud-based, and collaborative computational modeling.<br><br>
          o2S2PARC was developed with funding from the Common Fund’s Stimulating Peripheral Activity to Relieve Conditions 
          (SPARC) Program to ensure sustainable, reproducible, and FAIR (findable, accessible, interoperable, reusable) 
          computational modeling in the field of bioelectronic medicine, from neural interfaces to peripheral nerve recruitment 
          and the ensuing impact on organ function.<br><br>
          For more information regarding the SPARC Program, see the <a href='https://sparc.science/' style='color: ${color}' target='_blank'>SPARC Portal</a>.`);
          introText.setValue(displayName + aboutText);
        });
    }
  }
});
