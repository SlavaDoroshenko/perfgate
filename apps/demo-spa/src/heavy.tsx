import { mount } from "./bootstrap";
import { HeavyApp } from "./HeavyApp";

mount((inject) => <HeavyApp inject={inject} />);
