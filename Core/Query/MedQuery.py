from Core.Query.BaseQuery import BaseQuery
from Core.Common.Logger import logger
from Core.Common.Constants import Retriever
from Core.Prompt import QueryPrompt
from typing import Union
import asyncio
# from torch_geometric.data import Data, InMemoryDataset
from typing import Any, Dict, List, Tuple, no_type_check
from pcst_fast import pcst_fast
import torch
import pandas as pd
import numpy as np
from tqdm import tqdm
from Core.Common.Utils import truncate_str_by_token_size, encode_string_by_tiktoken
from Core.Common.Constants import GRAPH_FIELD_SEP
import time
from Core.Utils.TokenCounter import count_output_tokens

class MedQuery(BaseQuery):
    def __init__(self, config, retriever_context):
        super().__init__(config, retriever_context)

    async def _concatenate_information(self, metagraph_relation: str, metagraph_edge: tuple[str, str]):
        metagraph_relation_seperated = metagraph_relation.split(GRAPH_FIELD_SEP)
        return list(map(lambda x: metagraph_edge[0] + " " + x + " " +metagraph_edge[1], metagraph_relation_seperated))


    async def _retrieve_relevant_contexts(self, query: str):
        # find the most relevant subgraph
        metagraph_nodes = set()
        iteration_count = 1
        while len(metagraph_nodes) < self.config.topk_entity:
            origin_nodes = await self._retriever.retrieve_relevant_content(seed=query,
                                                                           top_k=self.config.topk_entity * iteration_count,
                                                                           type=Retriever.ENTITY,
                                                                           mode="vdb")  # list[dict]
            for node in origin_nodes[(iteration_count - 1) * self.config.topk_entity:]:
                if node["entity_name"] not in metagraph_nodes:
                    metagraph_nodes.add(node["entity_name"])

            iteration_count += 1

        print("Find top {} entities at iteration {}: {}".format(self.config.topk_entity, iteration_count, metagraph_nodes))

        # metagraph_nodes = await self._retriever.retrieve_relevant_content(seed=list(metagraph_nodes), k=self.config.k_hop, type=Retriever.SUBGRAPH, mode="k_hop_return_set") # return set
        # metagraph = await self._retriever.retrieve_relevant_content(seed=list(metagraph_nodes), type=Retriever.SUBGRAPH, mode="induced_subgraph_return_networkx")  # return networkx
        # metagraph_edges = list(metagraph.edges())

        # 一跳邻居：仅获取初始实体的一跳邻居集合
        one_hop_neighbors = await self._retriever.retrieve_relevant_content(
            seed=list(metagraph_nodes), k=1, type=Retriever.SUBGRAPH, mode="k_hop_return_set"
        )  # return set
        # 用 初始实体 ∪ 一跳邻居 诱导子图
        induced_nodes = set(metagraph_nodes)
        if one_hop_neighbors:
            induced_nodes.update(one_hop_neighbors)
        metagraph = await self._retriever.retrieve_relevant_content(
            seed=list(induced_nodes), type=Retriever.SUBGRAPH, mode="induced_subgraph_return_networkx"
        )  # return networkx
        # 仅保留 原始实体集合(S) 与 一跳邻居集合(N1) 的跨集边
        S = set(metagraph_nodes)
        N1 = set(one_hop_neighbors) if one_hop_neighbors else set()
        metagraph_edges_all = list(metagraph.edges())
        metagraph_edges = [
            (u, v)
            for (u, v) in metagraph_edges_all
            if (u in S and v in N1) or (v in S and u in N1)
        ]
        if not metagraph_edges:
            return ""
        
        metagraph_super_relations = await self._retriever.retrieve_relevant_content(seed=metagraph_edges, type=Retriever.RELATION, mode="by_source&target") # super relations
        zip_combined = tuple(zip(metagraph_super_relations, metagraph_edges))
        metagraph_concatenate = await asyncio.gather(*[self._concatenate_information(metagraph_super_relation, metagraph_edge) for metagraph_super_relation, metagraph_edge in zip_combined]) # list[list]
        print(f"Number of the metagraph: {len(metagraph_concatenate)}")
        context = ""
        for relations in metagraph_concatenate:
            if len(metagraph_concatenate) > 250:
                if len(relations) > 120:
                    print(f"Truncate relations from {len(relations)} to 120")
                    relations = relations[:120]
            elif len(metagraph_concatenate) > 100:
                if len(relations) > 200:
                    print(f"Truncate relations from {len(relations)} to 200")
                    relations = relations[:200]
            else:
                if len(relations) > 300:
                    print(f"Truncate relations from {len(relations)} to 300")
                    relations = relations[:300]
            context += ", ".join(relations)
            context += ", "

        def token_len(text: str) -> int:
            try:
                return len(encode_string_by_tiktoken(text))
            except Exception:
                return len(text)
        if token_len(context) > 30000:
            context = truncate_str_by_token_size(context, 30000)
        return context



    async def query(self, query):
        pcst_start = time.time()
        context = await self._retrieve_relevant_contexts(query)
        # print('Information:', context)
        print(f"Average retrival time={(time.time()-pcst_start):.4f}s ")
        response = await self.generation_qa(query, context)
        print(f"Time after llm={(time.time()-pcst_start):.4f}s ")
        model = (self.llm.config.model if hasattr(self.llm, "config") and getattr(self.llm.config, "model", None) else "gpt-3.5-turbo-0125") or "gpt-3.5-turbo-0125"
        print("Average tokens:", count_output_tokens(context, model))
        return response

    async def generation_qa(self, query: str, context: str):
        messages = [{"role": "system", "content": "You are an AI assistant that helps people find information."},
                    {"role": "user", "content": (
                        "the question is: " + query + 
                        ", the provided information is (list seperated by ,): " + context +
                        ". Now, generate exactly 10 candidate answers you believe are most likely. Do not say you don't know. "
                        "Output strictly in the format: "
                        "answer1:\"...\", answer2:\"...\", answer3:\"...\", answer4:\"...\", answer5:\"...\", "
                        "answer6:\"...\", answer7:\"...\", answer8:\"...\", answer9:\"...\", answer10:\"...\"."
                    )}]
        response = await self.llm.aask(msg=messages)
        return response

    async def generation_summary(self, query, context):
        if context is None:
            return QueryPrompt.FAIL_RESPONSE