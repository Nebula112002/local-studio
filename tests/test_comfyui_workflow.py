import unittest

from server.backends.base import GenerationParams
from server.backends.comfyui import ComfyUIBackend


def _params(**overrides) -> GenerationParams:
    base = dict(
        prompt="a cat",
        sampler="dpmpp_2m",
        scheduler="karras",
        steps=40,
        cfg_scale=5.5,
        clip_skip=2,
        seed=42,
        width=768,
        height=1024,
    )
    base.update(overrides)
    return GenerationParams(**base)


class ComfyUIWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = ComfyUIBackend("http://127.0.0.1:8188")

    def test_txt2img_uses_sampler_scheduler_and_clip_skip(self) -> None:
        workflow = self.backend._build_txt2img_workflow(_params())
        sampler = workflow["3"]["inputs"]
        self.assertEqual(sampler["sampler_name"], "dpmpp_2m")
        self.assertEqual(sampler["scheduler"], "karras")
        self.assertEqual(sampler["steps"], 40)
        self.assertEqual(sampler["cfg"], 5.5)
        self.assertEqual(sampler["seed"], 42)
        self.assertEqual(workflow["12"]["class_type"], "CLIPSetLastLayer")
        self.assertEqual(workflow["12"]["inputs"]["stop_at_clip_layer"], -2)
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["12", 0])
        self.assertEqual(workflow["7"]["inputs"]["clip"], ["12", 0])

    def test_txt2img_skips_clip_node_when_clip_skip_is_1(self) -> None:
        workflow = self.backend._build_txt2img_workflow(_params(clip_skip=1))
        self.assertNotIn("12", workflow)
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["4", 1])

    def test_img2img_uses_sampler(self) -> None:
        workflow = self.backend._build_img2img_workflow(_params(), "source.png")
        self.assertEqual(workflow["3"]["inputs"]["sampler_name"], "dpmpp_2m")
        self.assertEqual(workflow["3"]["inputs"]["scheduler"], "karras")
        self.assertEqual(workflow["12"]["inputs"]["stop_at_clip_layer"], -2)

    def test_reported_seed_matches_ksampler(self) -> None:
        workflow = self.backend._build_txt2img_workflow(_params(seed=-1))
        self.assertEqual(
            self.backend._sampler_seed(workflow),
            workflow["3"]["inputs"]["seed"],
        )
        self.assertGreaterEqual(workflow["3"]["inputs"]["seed"], 0)


if __name__ == "__main__":
    unittest.main()
