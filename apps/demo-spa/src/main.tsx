import { App } from "./App";
import { mount } from "./bootstrap";

mount((inject) => <App inject={inject} />);
