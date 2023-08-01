from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM

from pydantic import Field, root_validator
from transformers import LlamaForCausalLM, LlamaTokenizer
from typing import Any, Dict, List, Mapping, Optional

import torch


class Llama2(LLM):
    """Wrapper around Llama2 large language model."""
    # 7b: "meta-llama/Llama-2-7b-chat-hf"
    # 13b: "meta-llama/Llama-2-13b-chat-hf"
    # 70b: "meta-llama/Llama-2-70b-chat-hf"
    model_name: str = Field("meta-llama/Llama-2-7b-chat-hf", alias="model")
    """Model name to use."""
    max_new_tokens: int = 4096
    """The maximum number of tokens to generate in the completion."""
    model: Any = None  #: :meta private:
    """LLM model object."""
    tokenizer: Any = None
    """LLM tokenizer object."""

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Initialize model and tokenizer using model_name."""
        # init model
        model = LlamaForCausalLM.from_pretrained(
            values["model_name"],
            return_dict=True,
            load_in_8bit=False,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        _ = model.eval()
        values["model"] = model

        # init tokenizer
        tokenizer = LlamaTokenizer.from_pretrained(values["model_name"])
        _ = tokenizer.add_special_tokens(
            {
            
                "pad_token": "<PAD>",
            }
        )
        values["tokenizer"] = tokenizer

        return values

    @property
    def _llm_type(self) -> str:
        return "custom"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model_name": self.model_name,
            "max_new_tokens": self.max_new_tokens,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        # if stop is not None:
        #     raise ValueError("stop kwargs are not permitted for now.")

        # tokenize prompt and send to device(s)
        batch = self.tokenizer(prompt, return_tensors="pt")
        batch = {k: v.to("cuda") for k, v in batch.items()}

        # execute model on prompt
        with torch.no_grad():
            outputs = self.model.generate(
                **batch,
                max_new_tokens=self.max_new_tokens,
                do_sample=False
            )

        # decode output
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return output_text
