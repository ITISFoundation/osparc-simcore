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

qx.Class.define("osparc.navigation.StopSlideshow", {
  extend: qx.ui.form.Button,

  construct: function() {
    this.base(arguments, this.tr("Stop Slideshow"));

    this.set({
      ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
      visibility: "excluded"
    });
    this.addListener("execute", () => this.fireEvent("slidesStop"), this);
  },

  events: {
    "slidesStop": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    }
  },

  members: {
    _applyStudy: function(study) {
      if (study) {
        study.getUi().getSlideshow().addListener("changeSlideshow", () => this.__evalSlidesStopButton());
        study.getUi().addListener("changeMode", () => this.__evalSlidesStopButton());
        this.__evalSlidesStopButton();
      }
    },

    __evalSlidesStopButton: function() {
      const study = this.getStudy();
      if (study) {
        const editorContext = this.getStudy().getUi().getMode();
        this.setVisibility(["guided", "app"].includes(editorContext) ? "visible" : "excluded");
      }
    }
  }
});
