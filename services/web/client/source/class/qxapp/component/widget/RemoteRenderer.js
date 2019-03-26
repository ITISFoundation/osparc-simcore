/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * A Canvas that renders the given jpeg image and sends pointer interactions to backend
 * via websocket
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const remoteRenderer = new qxapp.component.widget.RemoteRenderer(node, webSocketUrl);
 *   this.getRoot().add(remoteRenderer);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.RemoteRenderer", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param webSocketUrl {string} webSocketUrl
  */
  construct: function(node, webSocketUrl) {
    this.base(arguments);

    this.set({
      node: node,
      webSocketUrl: webSocketUrl
    });

    this._setLayout(new qx.ui.layout.Canvas());

    const backgroundImage = this.__backgroundImage = new qx.ui.basic.Image().set({
      scale: true
    });
    this._add(backgroundImage, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    this.__counter = 0;
    this.addListenerOnce("appear", () => {
      const elem = this.getContentElement().getDomElement();
      const events = [
        "pointerdown",
        "pointerup",
        "tap",
        "dbltap",
        "longtap",
        "pointermove",
        "pointerover",
        "pointerout",
        "swipe",
        "track",
        "rotate",
        "pinch"
      ];
      events.forEach(event => {
        qx.bom.Element.addListener(elem, event, this.__logPointerEvent, this);
      }, this);

      this.addListener("resize", this.__resize, this);
      this.__requestScreenshot();
    }, this);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    webSocketUrl: {
      check: "String",
      nullable: true
    }
  },

  members: {
    __resize: function(e) {
      const width = e.getData().width;
      const height = e.getData().height;
      const data = {
        width: width,
        height: height
      };
      this.__backgroundImage.set({
        width: width,
        height: height
      });
      this.__requestScreenshot();
      console.log(data);
    },

    __logPointerEvent: function(pointerEvent) {
      pointerEvent.preventDefault();

      const evType = pointerEvent.getType();
      const evButton = pointerEvent.getButton();
      const evXPos = pointerEvent.getDocumentLeft();
      const evYPos = pointerEvent.getDocumentTop();
      const docWidth = this.getBounds().width;
      const docHeight = this.getBounds().height;
      const evXPosRel = evXPos / docWidth;
      const evYPosRel = evYPos / docHeight;
      console.log(evType, evButton, evXPos, evYPos, evXPosRel, evYPosRel);
      this.__requestScreenshot();
    },

    __requestScreenshot: function() {
      const latency = 100;
      qx.event.Timer.once(e => {
        const imageUrl = this.__getAScreenshot();
        this.__updateScreenshot(imageUrl);
      }, this, latency);
    },

    __updateScreenshot: function(image) {
      this.__backgroundImage.setSource(image);
    },

    __getAScreenshot: function() {
      const images = [
        "00",
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11"
      ];
      const imageUrl = "qxapp/Horse_" + images[this.__counter] + ".png";
      this.__counter++;
      if (this.__counter === images.length) {
        this.__counter = 0;
      }
      return imageUrl;
    }
  }
});
