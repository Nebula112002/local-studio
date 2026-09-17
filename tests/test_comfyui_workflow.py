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


WAN_OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": [["epicrealismXL_pureFix.safetensors", "juggernautXL_ragnarokBy.safetensors"]]}}
    },
    "ImageOnlyCheckpointLoader": {
        "input": {"required": {"ckpt_name": [["epicrealismXL_pureFix.safetensors", "juggernautXL_ragnarokBy.safetensors"]]}}
    },
    "UNETLoader": {
        "input": {
            "required": {
                "unet_name": [[
                    "flux1-dev.safetensors",
                    "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                    "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                    "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                    "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                ]]
            }
        }
    },
    "CLIPLoader": {
        "input": {"required": {"clip_name": [["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "clip_l.safetensors"]]}}
    },
    "VAELoader": {
        "input": {"required": {"vae_name": [["wan_2.1_vae.safetensors", "wan2.2_vae.safetensors", "ae.safetensors"]]}}
    },
    "LoraLoaderModelOnly": {
        "input": {
            "required": {
                "lora_name": [[
                    "DaSiWa_LTX23_NSFW_Bodyphysics_Fluid_Motion_Enhancer_v01.safetensors",
                    "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                    "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                    "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
                    "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
                ]]
            }
        }
    },
    "KSampler": {"input": {"required": {"sampler_name": [["euler"]], "scheduler": [["simple", "normal"]]}}},
    "CLIPVisionLoader": {"input": {"required": {"clip_name": [["clip_vision_h.safetensors"]]}}},
    "CLIPVisionEncode": {},
    "EmptyHunyuanLatentVideo": {},
    "Wan22ImageToVideoLatent": {},
    "WanImageToVideo": {},
    "CreateVideo": {},
    "SaveVideo": {},
    "SVD_img2vid_Conditioning": {},
}

SVD_OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": [["epicrealismXL_pureFix.safetensors", "svd_xt.safetensors"]]}}
    },
    "ImageOnlyCheckpointLoader": {
        "input": {"required": {"ckpt_name": [["epicrealismXL_pureFix.safetensors", "svd_xt.safetensors"]]}}
    },
    "UNETLoader": {"input": {"required": {"unet_name": [[]]}}},
    "KSampler": {"input": {"required": {"sampler_name": [["euler"]], "scheduler": [["normal"]]}}},
    "SVD_img2vid_Conditioning": {},
    "CreateVideo": {},
    "SaveVideo": {},
}


class ComfyUIVideoWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = ComfyUIBackend("http://127.0.0.1:8188")
        self.backend._object_info = WAN_OBJECT_INFO

    def test_video_models_are_wan_not_sdxl(self) -> None:
        import asyncio

        info = asyncio.run(self.backend.get_info())
        self.assertEqual(
            info.video_models,
            [
                "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
            ],
        )
        self.assertIn("txt2video", info.capabilities)
        self.assertIn("img2video", info.capabilities)
        self.assertNotIn("epicrealismXL_pureFix.safetensors", info.video_models)

    def test_svd_node_without_svd_checkpoint_does_not_enable_video(self) -> None:
        import asyncio

        self.backend._object_info = {
            **WAN_OBJECT_INFO,
            "UNETLoader": {"input": {"required": {"unet_name": [["flux1-dev.safetensors"]]}}},
            "ImageOnlyCheckpointLoader": {
                "input": {"required": {"ckpt_name": [["epicrealismXL_pureFix.safetensors"]]}}
            },
        }
        info = asyncio.run(self.backend.get_info())
        self.assertEqual(info.video_models, [])
        self.assertNotIn("txt2video", info.capabilities)

    def test_wan_txt2video_uses_lightning_pair(self) -> None:
        workflow = self.backend._build_wan_workflow(_params(mode="txt2video", frames=60, steps=25, cfg_scale=3.5))
        self.assertEqual(workflow["10"]["inputs"]["unet_name"], "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors")
        self.assertEqual(workflow["10b"]["inputs"]["unet_name"], "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors")
        self.assertEqual(workflow["13"]["inputs"]["type"], "wan")
        self.assertEqual(workflow["20"]["class_type"], "EmptyHunyuanLatentVideo")
        self.assertEqual(workflow["20"]["inputs"]["length"], 61)
        self.assertEqual(workflow["21"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["21"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["21"]["inputs"]["end_at_step"], 2)
        self.assertEqual(workflow["22"]["inputs"]["start_at_step"], 2)
        self.assertEqual(workflow["21"]["class_type"], "KSamplerAdvanced")
        self.assertNotIn("18", workflow)

    def test_wan_img2video_uses_start_image_latent(self) -> None:
        workflow = self.backend._build_wan_workflow(
            _params(mode="img2video", frames=60, width=1024, height=576),
            "source.png",
        )
        self.assertEqual(workflow["10"]["inputs"]["unet_name"], "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors")
        self.assertEqual(workflow["18"]["class_type"], "LoadImage")
        self.assertEqual(workflow["20"]["class_type"], "WanImageToVideo")
        self.assertEqual(workflow["20"]["inputs"]["start_image"], ["18", 0])
        self.assertEqual(workflow["17"]["class_type"], "CLIPVisionLoader")
        self.assertLessEqual(workflow["20"]["inputs"]["width"] * workflow["20"]["inputs"]["height"], 640 * 480)
        self.assertEqual(workflow["20"]["inputs"]["length"], 61)
        self.assertEqual(workflow["14"]["inputs"]["vae_name"], "wan_2.1_vae.safetensors")

    def test_wan_5b_uses_wan22_latent(self) -> None:
        self.backend._object_info = {
            **WAN_OBJECT_INFO,
            "UNETLoader": {
                "input": {"required": {"unet_name": [["wan2.2_ti2v_5B_fp16.safetensors"]]}}
            },
            "LoraLoaderModelOnly": {"input": {"required": {"lora_name": [[]]}}},
        }
        workflow = self.backend._build_wan_workflow(
            _params(mode="img2video", frames=49, width=768, height=432),
            "source.png",
        )
        self.assertEqual(workflow["20"]["class_type"], "Wan22ImageToVideoLatent")
        self.assertEqual(workflow["14"]["inputs"]["vae_name"], "wan2.2_vae.safetensors")
        self.assertNotIn("10b", workflow)

    def test_sdxl_video_model_is_ignored_for_wan_bundle(self) -> None:
        bundle = self.backend._resolve_wan_bundle(
            _params(mode="txt2video", video_model="epicrealismXL_pureFix.safetensors")
        )
        self.assertTrue(bundle["high_unet"].startswith("wan2.2_t2v_high_noise"))
        self.assertTrue(bundle["lightning"])

    def test_svd_fallback_keeps_svd_checkpoint(self) -> None:
        self.backend._object_info = SVD_OBJECT_INFO
        workflow = self.backend._build_svd_workflow(_params(mode="img2video"), "source.png")
        self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], "svd_xt.safetensors")
        self.assertEqual(workflow["3"]["class_type"], "SVD_img2vid_Conditioning")

    def test_history_error_surfaces_comfy_message(self) -> None:
        message = ComfyUIBackend._history_error({
            "status": {
                "status_str": "error",
                "completed": False,
                "messages": [[
                    "execution_error",
                    {
                        "node_type": "SVD_img2vid_Conditioning",
                        "exception_message": "'NoneType' object has no attribute 'encode_image'\n",
                    },
                ]],
            }
        })
        self.assertIn("SVD_img2vid_Conditioning", message)
        self.assertIn("encode_image", message)

    def test_sampler_seed_reads_advanced_noise_seed(self) -> None:
        workflow = self.backend._build_wan_workflow(_params(mode="txt2video", seed=99))
        self.assertEqual(self.backend._sampler_seed(workflow), 99)

    def test_wan_honors_user_fps_and_frames(self) -> None:
        workflow = self.backend._build_wan_workflow(
            _params(mode="txt2video", frames=60, fps=10, width=640, height=384)
        )
        self.assertEqual(workflow["20"]["inputs"]["length"], 61)
        self.assertEqual(workflow["31"]["inputs"]["fps"], 10)
        self.assertEqual(workflow["20"]["inputs"]["width"], 640)
        self.assertEqual(workflow["20"]["inputs"]["height"], 384)

    def test_wan_motion_maps_to_shift(self) -> None:
        quiet = self.backend._build_wan_workflow(_params(mode="txt2video", motion_bucket_id=64))
        lively = self.backend._build_wan_workflow(_params(mode="txt2video", motion_bucket_id=180))
        self.assertLess(quiet["11"]["inputs"]["shift"], lively["11"]["inputs"]["shift"])
        self.assertGreaterEqual(lively["11"]["inputs"]["shift"], 9.0)
        self.assertAlmostEqual(self.backend._wan_shift(127), 8.0)
        self.assertAlmostEqual(self.backend._wan_shift(180), 9.66)


if __name__ == "__main__":
    unittest.main()
