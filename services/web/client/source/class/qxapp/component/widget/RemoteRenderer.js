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
 *   const remoteRenderer = new qxapp.component.widget.RemoteRenderer(webSocketUrl);
 *   this.getRoot().add(remoteRenderer);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.RemoteRenderer", {
  extend: qx.ui.core.Widget,

  /**
    * @param webSocketUrl {string} webSocketUrl
  */
  construct: function(webSocketUrl) {
    this.base(arguments);

    this.set({
      webSocketUrl: webSocketUrl
    });

    this._setLayout(new qx.ui.layout.Canvas());

    const backgroundImage = this.__backgroundImage = new qx.ui.basic.Image().set({
      allowGrowX: true,
      allowGrowY: true,
      allowShrinkX: true,
      allowShrinkY: true,
      scale: true
    });
    const padding = 0; // different padding to 0 triggers resize...
    this._add(backgroundImage, {
      top: padding,
      right: padding,
      bottom: padding,
      left: padding
    });

    this.__counter = 0;
    // --------- x,y
    // -------------
    // -------------
    // 0,0 ---------
    this.addListenerOnce("appear", () => {
      const elem = this.getContentElement().getDomElement();
      const events = [
        "pointerdown",
        "pointerup",
        "tap",
        "dbltap",
        "mousewheel",
        "pointermove"
      ];
      events.forEach(event => {
        qx.bom.Element.addListener(elem, event, this.__logPointerEvent, this);
      }, this);

      this.addListener("resize", this.__resize, this);

      this.__requestScreenshot();
    }, this);
  },

  properties: {
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
      /*
      const pevType = pointerEvent.getType();
      const pevBtn = pointerEvent.getButton();
      const pevDocL = pointerEvent.getDocumentLeft();
      const pevDocT = pointerEvent.getDocumentTop();
      const pevVpL = pointerEvent.getViewportLeft();
      const pevVpT = pointerEvent.getViewportTop();
      console.log("Pointer Event", pevType, pevBtn, pevDocL, pevDocT, pevVpL, pevVpT);

      const bcrPos = this.getBounds();
      console.log("Window", bcrPos);
      */
      const navBarHeight = 50;
      const pPosX = pointerEvent.getViewportLeft() - this.getBounds().left;
      const pPosY = this.getBounds().height + navBarHeight - pointerEvent.getViewportTop();
      const pevType = pointerEvent.getType();
      switch (pevType) {
        // case "tap":
        case "pointerdown":
        case "pointerup":
        case "dbltap": {
          const pevBtn = pointerEvent.getButton();
          let what = 0;
          switch (pevType) {
            case "pointerdown":
              what = 1;
              break;
            case "pointerup":
              what = 2;
              break;
            case "dbltap":
              what = 3;
              break;
          }
          console.log("OnMouseButton", pPosX, pPosY, pevBtn, what);
          break;
        }
        case "mousewheel": {
          const pevWD = pointerEvent.getWheelDelta();
          console.log("OnMouseWheel", pPosX, pPosY, pevWD);
          break;
        }
        case "pointermove": {
          console.log("OnMouseMove", pPosX, pPosY);
          break;
        }
        default: {
          console.log("Other type", pevType);
          break;
        }
      }

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
      const nImages = 23;
      const pad = "000";
      const images = [];
      for (let i=1; i<=nImages; i++) {
        const str = String(i);
        const padded = pad.substring(0, pad.length - str.length) + str;
        images.push(padded);
      }
      const imageUrl = "qxapp/S4L_" + images[this.__counter] + ".png";
      this.__counter++;
      if (this.__counter === images.length) {
        this.__counter = 0;
      }
      return imageUrl;
    }
  }
});
